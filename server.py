"""Small local server for the microphone recorder."""
import os
import tempfile
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import imageio_ffmpeg
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
import whisperx

app = FastAPI()
RECORDINGS_DIRECTORY = Path(__file__).with_name("recordings")
MODEL_NAME = os.getenv("WHISPERX_MODEL", "base")
DEVICE = os.getenv("WHISPERX_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPERX_COMPUTE_TYPE", "int8" if DEVICE == "cpu" else "float16")
model = None


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


@app.get("/")
def page():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/recordings/{filename}")
def recording(filename: str):
    path = RECORDINGS_DIRECTORY / Path(filename).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Recording not found.")
    return FileResponse(path, media_type="audio/webm", filename=path.name)


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    temp_path = None
    saved_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            temp_file.write(await audio.read())

        RECORDINGS_DIRECTORY.mkdir(exist_ok=True)
        saved_name = f"recording-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}{suffix}"
        saved_path = RECORDINGS_DIRECTORY / saved_name
        saved_path.write_bytes(Path(temp_path).read_bytes())

        result = get_model().transcribe(load_audio(str(saved_path)))
        segments = [
            {"start": segment["start"], "end": segment["end"], "text": segment["text"].strip()}
            for segment in result["segments"]
        ]
        text = " ".join(segment["text"] for segment in segments).strip()
        transcript_path = saved_path.with_suffix(".json")
        transcript_path.write_text(
            json.dumps({"recording": saved_name, "text": text, "segments": segments}, indent=2),
            encoding="utf-8",
        )
        return {"text": text, "segments": segments, "recording_url": f"/recordings/{saved_name}"}
    except Exception as exc:
        if saved_path:
            saved_path.unlink(missing_ok=True)
            saved_path.with_suffix(".json").unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
