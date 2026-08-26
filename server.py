"""Small local server for the microphone recorder."""
import os
import tempfile
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import imageio_ffmpeg
import numpy as np
import pandas as pd
import torch
from dotenv import load_dotenv
from fastapi import FastAPI, Body, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
import whisperx
from whisperx.diarize import DiarizationPipeline

app = FastAPI()
load_dotenv(Path(__file__).with_name(".env"))
RECORDINGS_DIRECTORY = Path(__file__).with_name("recordings")
SYNTHETIC_TRANSCRIPT = Path(__file__).with_name("synthetic_conversation.json")
MODEL_NAME = os.getenv("WHISPERX_MODEL", "base")
DEVICE = os.getenv("WHISPERX_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPERX_COMPUTE_TYPE", "int8" if DEVICE == "cpu" else "float16")
HF_TOKEN = os.getenv("HF_TOKEN")
ENABLE_DIARIZATION = os.getenv("WHISPERX_DIARIZE", "true" if HF_TOKEN else "false").lower() == "true"
# Therapy sessions normally have two participants. Supplying this to pyannote
# prevents it from collapsing similar synthetic voices into one cluster. Set
# WHISPERX_NUM_SPEAKERS=0 to let pyannote infer the count instead.
EXPECTED_SPEAKERS = int(os.getenv("WHISPERX_NUM_SPEAKERS", "2"))
# A speaker change shorter than this is usually a word-level clustering glitch,
# not a conversational handoff.
MIN_SPEAKER_TURN_SECONDS = float(os.getenv("WHISPERX_MIN_TURN_SECONDS", "0.5"))
model = None
diarization_model = None
alignment_models: dict[str, tuple[Any, dict[str, Any]]] = {}


def load_audio(file_path: str, sample_rate: int = 16000) -> np.ndarray:
    """Decode browser audio with the portable FFmpeg bundled by imageio-ffmpeg."""
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-nostdin", "-i", file_path, "-f", "s16le", "-ac", "1",
        "-acodec", "pcm_s16le", "-ar", str(sample_rate), "-",
    ]
    import subprocess
    output = subprocess.run(command, capture_output=True, check=True).stdout
    return np.frombuffer(output, np.int16).astype(np.float32) / 32768.0


def get_model():
    global model
    if model is None:
        model = whisperx.load_model(MODEL_NAME, DEVICE, compute_type=COMPUTE_TYPE)
    return model


def get_diarization_model():
    """Load pyannote diarization only when it is configured for use."""
    global diarization_model
    if not HF_TOKEN:
        raise HTTPException(
            status_code=400,
            detail="Diarization needs an HF_TOKEN. Set it after accepting the pyannote model terms.",
        )
    if diarization_model is None:
        diarization_model = DiarizationPipeline(token=HF_TOKEN, device=DEVICE)
    return diarization_model


def get_alignment_model(language: str):
    """Load and cache WhisperX's word-timestamp model for a language."""
    if language not in alignment_models:
        alignment_models[language] = whisperx.load_align_model(
            language_code=language,
            device=DEVICE,
        )
    return alignment_models[language]


def diarize_exclusively(audio_data: np.ndarray):
    """Return one non-overlapping speaker timeline plus serializable diagnostics.

    WhisperX's wrapper returns the regular diarization annotation. It can contain
    overlapping tracks, which lets a brief second track steal a word during
    speaker assignment. Community-1 also exposes an *exclusive* annotation:
    exactly one speaker at any instant, which is the appropriate timeline for
    a sequential therapy conversation.
    """
    pipeline = get_diarization_model().model
    output = pipeline(
        {"waveform": torch.from_numpy(audio_data[None, :]), "sample_rate": 16000},
        **({"num_speakers": EXPECTED_SPEAKERS} if EXPECTED_SPEAKERS > 0 else {}),
    )
    annotation = output.exclusive_speaker_diarization
    diarization = pd.DataFrame(
        annotation.itertracks(yield_label=True),
        columns=["segment", "label", "speaker"],
    )
    diarization["start"] = diarization["segment"].apply(lambda segment: segment.start)
    diarization["end"] = diarization["segment"].apply(lambda segment: segment.end)
    debug_turns = [
        {"start": row.start, "end": row.end, "speaker": row.speaker}
        for row in diarization.itertuples(index=False)
    ]
    return diarization, debug_turns


def speaker_turns(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Split aligned ASR segments wherever the diarized word speaker changes."""
    turns = []

    def append_turn(turn):
        text = " ".join(word for word in turn.pop("words") if word).strip()
        if not text:
            return
        if turn["speaker"] is None:
            turn.pop("speaker")
        turns.append({**turn, "text": text})

    for segment in result.get("segments", []):
        words = [
            word for word in segment.get("words", [])
            if word.get("start") is not None and word.get("end") is not None
        ]
        if not words:
            # Keep unalignable speech instead of silently dropping it.
            turns.append({
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"].strip(),
                **({"speaker": segment["speaker"]} if segment.get("speaker") else {}),
            })
            continue

        current = None
        for word in words:
            speaker = word.get("speaker") or segment.get("speaker")
            if current is None or speaker != current["speaker"]:
                if current is not None:
                    append_turn(current)
                current = {
                    "start": word["start"],
                    "end": word["end"],
                    "speaker": speaker,
                    "words": [],
                }
            current["end"] = word["end"]
            current["words"].append(str(word.get("word", "")).strip())

        if current is not None:
            append_turn(current)

    # Alignment often creates sentence-sized ASR segments. Merge adjacent pieces
    # spoken by the same diarized person, so a UI item represents a turn rather
    # than an arbitrary Whisper pause.
    merged = []
    for turn in turns:
        if (
            merged
            and turn.get("speaker") == merged[-1].get("speaker")
            and turn["start"] >= merged[-1]["end"]
        ):
            merged[-1]["end"] = turn["end"]
            merged[-1]["text"] = f"{merged[-1]['text']} {turn['text']}"
        else:
            merged.append(turn)

    # Reassign isolated, sub-second label blips to their surrounding speaker.
    # This prevents a stray word from becoming a clickable turn of its own.
    index = 1
    while index < len(merged) - 1:
        previous, current, following = merged[index - 1:index + 2]
        if (
            current["end"] - current["start"] < MIN_SPEAKER_TURN_SECONDS
            and previous.get("speaker") == following.get("speaker")
        ):
            previous["end"] = following["end"]
            previous["text"] = f"{previous['text']} {current['text']} {following['text']}"
            merged.pop(index + 1)
            merged.pop(index)
        else:
            index += 1
    return merged


def transcript_path_for(transcript_id: str) -> Path:
    """Resolve a transcript ID to a local JSON file without allowing path traversal."""
    if transcript_id == "synthetic":
        return SYNTHETIC_TRANSCRIPT
    if transcript_id.startswith("legacy-"):
        return RECORDINGS_DIRECTORY / Path(transcript_id.removeprefix("legacy-")).name
    return RECORDINGS_DIRECTORY / Path(transcript_id).name / "transcript.json"


@app.get("/")
def page():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/recordings/{session_id}/{filename}")
def session_recording(session_id: str, filename: str):
    """Serve an audio file belonging to one saved session."""
    path = RECORDINGS_DIRECTORY / Path(session_id).name / Path(filename).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Recording not found.")
    return FileResponse(path, media_type="audio/webm", filename=path.name)


@app.get("/recordings/{filename}")
def legacy_recording(filename: str):
    """Serve recordings saved by versions before session folders were introduced."""
    path = RECORDINGS_DIRECTORY / Path(filename).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Recording not found.")
    return FileResponse(path, media_type="audio/webm", filename=path.name)


@app.get("/transcripts")
def transcripts():
    """List locally saved transcripts, newest first."""
    items = []
    transcript_paths = list(RECORDINGS_DIRECTORY.glob("*/transcript.json")) if RECORDINGS_DIRECTORY.exists() else []
    transcript_paths.extend(RECORDINGS_DIRECTORY.glob("*.json") if RECORDINGS_DIRECTORY.exists() else [])
    if SYNTHETIC_TRANSCRIPT.is_file():
        transcript_paths.append(SYNTHETIC_TRANSCRIPT)
    for transcript_path in transcript_paths:
        try:
            data = json.loads(transcript_path.read_text(encoding="utf-8"))
            modified = datetime.fromtimestamp(transcript_path.stat().st_mtime)
            is_session = transcript_path.name == "transcript.json" and transcript_path.parent != RECORDINGS_DIRECTORY
            transcript_id = transcript_path.parent.name if is_session else f"legacy-{transcript_path.name}"
            if transcript_path == SYNTHETIC_TRANSCRIPT:
                transcript_id = "synthetic"
            items.append({
                "id": transcript_id,
                "label": data.get("title") or data.get("recording") or transcript_path.parent.name,
                "text": data.get("text", ""),
                "created_at": data.get("created_at") or data.get("createdAt") or modified.isoformat(timespec="seconds"),
            })
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(items, key=lambda item: item["created_at"], reverse=True)


@app.get("/transcripts/{transcript_id}")
def transcript(transcript_id: str):
    """Return one saved transcript JSON file."""
    path = transcript_path_for(transcript_id)
    if path.suffix != ".json" or not path.is_file():
        raise HTTPException(status_code=404, detail="Transcript not found.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        audio = data.get("audio")
        if audio and audio.get("file") and path.parent != RECORDINGS_DIRECTORY:
            data["recording_url"] = f"/recordings/{path.parent.name}/{audio['file']}"
        elif data.get("recording"):
            data["recording_url"] = f"/recordings/{data['recording']}"
        return data
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Transcript file is invalid JSON.") from exc


@app.put("/transcripts/{transcript_id}/speakers")
def save_speaker_labels(transcript_id: str, labels: dict[str, str] = Body(...)):
    """Persist user-friendly names for diarized speaker IDs."""
    path = transcript_path_for(transcript_id)
    if transcript_id == "synthetic" or not path.is_file():
        raise HTTPException(status_code=404, detail="Transcript not found.")
    cleaned_labels = {
        key.strip(): value.strip()
        for key, value in labels.items()
        if isinstance(key, str) and isinstance(value, str) and key.strip() and value.strip()
    }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["speakers"] = cleaned_labels
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"speakers": cleaned_labels}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="Transcript file is invalid JSON.") from exc


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    temp_path = None
    session_directory = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            temp_file.write(await audio.read())

        RECORDINGS_DIRECTORY.mkdir(exist_ok=True)
        session_id = f"session-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
        session_directory = RECORDINGS_DIRECTORY / session_id
        session_directory.mkdir()
        saved_name = f"recording{suffix}"
        saved_path = session_directory / saved_name
        saved_path.write_bytes(Path(temp_path).read_bytes())

        audio_data = load_audio(str(saved_path))
        result = get_model().transcribe(audio_data)
        if ENABLE_DIARIZATION:
            language = result.get("language")
            if not language:
                raise RuntimeError("WhisperX did not return a language for word alignment.")
            align_model, align_metadata = get_alignment_model(language)
            result = whisperx.align(
                result["segments"], align_model, align_metadata, audio_data, DEVICE,
                return_char_alignments=False,
            )
            diarize_segments, diarization_debug = diarize_exclusively(audio_data)
            result = whisperx.assign_word_speakers(diarize_segments, result)
        segments = speaker_turns(result) if ENABLE_DIARIZATION else [
            {
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"].strip(),
            }
            for segment in result["segments"]
        ]
        text = " ".join(segment["text"] for segment in segments).strip()
        transcript_path = session_directory / "transcript.json"
        created_at = datetime.now().astimezone().isoformat(timespec="seconds")
        duration = segments[-1]["end"] if segments else 0
        transcript_path.write_text(
            json.dumps({
                "id": session_id,
                "created_at": created_at,
                "audio": {"file": saved_name, "mime_type": "audio/webm", "duration_seconds": duration},
                "speakers": {},
                "diarization": diarization_debug if ENABLE_DIARIZATION else [],
                "text": text,
                "segments": segments,
            }, indent=2),
            encoding="utf-8",
        )
        return {"id": session_id, "text": text, "segments": segments, "recording_url": f"/recordings/{session_id}/{saved_name}"}
    except Exception as exc:
        if session_directory:
            shutil.rmtree(session_directory, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
