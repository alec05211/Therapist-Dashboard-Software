"""Synthesize a two-speaker script with Gemini 3.8 TTS and join the WAV parts."""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CREDENTIALS = ROOT / ".secrets" / "google_tts-script-runner_key.json"
DEFAULT_MODEL = "gemini-3.8-flash-tts"
REALISM_POLICY_PATH = ROOT / "docs" / "ai" / "SYNTHETIC_SESSION_REALISM.md"
PART_HEADING = re.compile(r"(?m)^## Part \d+[^\n]*\n")
LEADING_DIRECTION = re.compile(r"^\[([^\]]+)\]\s*")
SILENCE_CUE = re.compile(r"^\[SILENCE\s*-\s*(\d+)\s*SECONDS?\s*-\s*DO NOT SPEAK\]$", re.I)
DISFLUENCY_CUE = re.compile(
    r"(?:\b(?:um+|uh+|erm+|wait|sorry)\b|\bi\s*[—-]|\.\.\.|\bno,\s+(?:that|wait)|\bthat's not (?:right|quite))",
    re.I,
)
UNCERTAIN_RECALL_CUE = re.compile(
    r"(?:\bi (?:do not|don't|can't) remember\b|\bi'm not sure\b|\bi (?:really )?don't know (?:when|whether|which|what)\b|\bi think it was\b|\bmaybe it was\b|\bnot (?:the )?exact words\b|\bsomething like\b|\bi lost my train of thought\b|\bblanked on it\b)",
    re.I,
)

REALISM_PREFLIGHT = """
=== REQUIRED SYNTHETIC SESSION REALISM PREFLIGHT ===
Policy: docs/ai/SYNTHETIC_SESSION_REALISM.md

NATIVE TIMING - NON-NEGOTIABLE
  Never globally slow, accelerate, interpolate, or time-stretch a recording.
  If native output misses the duration target, revise the script or real silence and render again.
  Sample-rate conversion is allowed only when duration and pitch remain unchanged.

DIALOGUE REVIEW
  - The client must not remember every quotation, sequence, or detail precisely.
  - Mix fragments, short answers, false starts, corrections, uncertainty, and incomplete thought.
  - Do not make every client turn polished, insightful, or clinically useful.
  - The therapist must not reflect perfectly or produce a formulation after every exchange.
  - Preserve ordinary confusion, repetition, topic drift, silence, missed interpretations,
    low-information stretches, disagreement, and unresolved material.
  - Spoken disfluencies must appear in the verbatim transcript; style metadata cannot invent them reliably.

CLINICAL BOUNDARY
  Vocal directions and generated hesitation are production choices, not clinical findings.
====================================================
""".strip()


def print_realism_preflight() -> None:
    print(REALISM_PREFLIGHT, flush=True)


def realism_report(parsed_parts: list[list[dict[str, str]]], client_alias: str, script: str) -> dict[str, int | float]:
    turns = [turn for part in parsed_parts for turn in part]
    client_turns = [turn for turn in turns if turn["speaker"] == client_alias]
    therapist_turns = [turn for turn in turns if turn["speaker"] != client_alias]
    client_word_counts = [len(re.findall(r"\b[\w'-]+\b", turn["text"])) for turn in client_turns]
    long_client_turns = sum(words >= 60 for words in client_word_counts)
    disfluent_client_turns = sum(bool(DISFLUENCY_CUE.search(turn["text"])) for turn in client_turns)
    uncertain_recall_turns = sum(bool(UNCERTAIN_RECALL_CUE.search(turn["text"])) for turn in client_turns)
    exact_silence_cues = sum(bool(SILENCE_CUE.match(line.strip())) for line in script.splitlines())
    return {
        "client_turns": len(client_turns),
        "therapist_turns": len(therapist_turns),
        "client_turns_60_words_or_more": long_client_turns,
        "client_turns_with_explicit_disfluency": disfluent_client_turns,
        "client_turns_with_uncertain_recall": uncertain_recall_turns,
        "exact_silence_cues": exact_silence_cues,
        "average_client_words_per_turn": round(sum(client_word_counts) / max(len(client_word_counts), 1), 1),
    }


def print_realism_report(report: dict[str, int | float]) -> None:
    print("\nScript realism indicators (review prompts, not proof of realism):", flush=True)
    for label, value in report.items():
        print(f"  {label}: {value}", flush=True)
    if report["client_turns_with_explicit_disfluency"] == 0:
        print("  WARNING: no explicit client disfluencies were detected.", flush=True)
    if report["client_turns_with_uncertain_recall"] == 0:
        print("  WARNING: no explicit uncertain-recall language was detected.", flush=True)
    if report["client_turns_60_words_or_more"] > report["client_turns"] * 0.25:
        print("  WARNING: more than 25% of client turns contain at least 60 words.", flush=True)
    print("A human listening/writing review remains required.\n", flush=True)


def parse_parts(script: str) -> list[str]:
    matches = list(PART_HEADING.finditer(script))
    if not matches:
        raise ValueError("Script must contain headings such as '## Part 1'.")
    parts: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(script)
        part = script[match.end():end].strip()
        if part:
            parts.append(part)
    return parts


def _replace_legacy_cues(text: str) -> str:
    replacements = {
        "[pause]": "<short pause>",
        "[long pause]": "<long pause>",
        "[sigh]": "<sigh>",
        "[laugh]": "<laugh>",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def parse_turns(part: str, speakers: tuple[str, str]) -> list[dict[str, str]]:
    turns: list[dict[str, str]] = []
    pending_pause_seconds = ""
    labels = {speaker.upper(): speaker for speaker in speakers}
    for raw_line in part.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        silence = SILENCE_CUE.match(line)
        if silence:
            pending_pause_seconds = silence.group(1)
            continue
        if ":" not in line:
            raise ValueError(f"Unrecognized script line: {line}")
        label, text = line.split(":", 1)
        speaker = labels.get(label.strip().upper())
        if not speaker:
            raise ValueError(f"Unknown speaker label: {label.strip()}")
        text = text.strip()
        direction = ""
        match = LEADING_DIRECTION.match(text)
        if match:
            direction = match.group(1).strip()
            text = text[match.end():].strip()
        text = _replace_legacy_cues(text)
        if not text:
            raise ValueError(f"Empty spoken turn for {speaker}")
        turns.append({
            "speaker": speaker,
            "text": text,
            "direction": direction,
            "pause_before_seconds": pending_pause_seconds,
        })
        pending_pause_seconds = ""
    if not turns:
        raise ValueError("Part contains no spoken turns.")
    for speaker in speakers:
        if not any(turn["speaker"] == speaker for turn in turns):
            raise ValueError(f"Part must contain at least one {speaker} turn.")
    return turns


def read_wave(audio: bytes) -> tuple[wave._wave_params, bytes]:
    with wave.open(io.BytesIO(audio), "rb") as source:
        return source.getparams(), source.readframes(source.getnframes())


def _audio_from_response(response) -> bytes:
    try:
        audio = response.candidates[0].content.parts[0].inline_data.data
    except (AttributeError, IndexError, TypeError) as exc:
        raise RuntimeError("Gemini returned no audio content.") from exc
    if not audio:
        raise RuntimeError("Gemini returned empty audio content.")
    return audio


def _style(base: str, segment: str, direction: str) -> str:
    values = [value.strip().rstrip(".") for value in (base, segment, direction) if value and value.strip()]
    return ". ".join(values) + "."


def _load_voice_config(path: Path | None) -> dict:
    if not path:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Dialogue script with ## Part N headings")
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--voice-config", type=Path, help="Client voice-config.json")
    parser.add_argument("--client-alias", default="CLIENT")
    parser.add_argument("--client-voice", "--marcus-voice", dest="client_voice", default="Kore")
    parser.add_argument("--client-style", default="Natural, restrained, conversational delivery")
    parser.add_argument("--therapist-alias", default="THERAPIST")
    parser.add_argument("--therapist-voice", "--jeremy-voice", dest="therapist_voice", default="Sadaltager")
    parser.add_argument("--therapist-style", default="Calm, concise, attentive, and unhurried")
    parser.add_argument("--prompt", help="Legacy shared style direction appended to both speakers")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--location", default="global")
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--acknowledge-realism-policy",
        action="store_true",
        help="Confirm the required native-timing and imperfect-dialogue preflight was read",
    )
    args = parser.parse_args()

    try:
        print_realism_preflight()
        if not args.acknowledge_realism_policy:
            raise ValueError(
                "Generation is blocked until --acknowledge-realism-policy is supplied after reviewing the preflight."
            )
        input_path = args.input.resolve()
        output_path = args.output.resolve()
        if output_path.suffix.lower() != ".wav":
            raise ValueError("Output must use a .wav extension.")
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(f"Output exists: {output_path}; pass --overwrite to replace it.")
        if not args.project:
            raise ValueError("Set GOOGLE_CLOUD_PROJECT or pass --project.")
        credentials_path = args.credentials.resolve()
        if not credentials_path.is_file():
            raise FileNotFoundError(f"Credential file not found: {credentials_path}")

        config = _load_voice_config(args.voice_config.resolve() if args.voice_config else None)
        client_config = config.get("client", {})
        therapist_config = config.get("therapist", {})
        args.model = config.get("model", args.model)
        args.location = config.get("location", args.location)
        args.client_alias = client_config.get("speaker_alias", args.client_alias)
        args.client_voice = client_config.get("provider_voice_reference", args.client_voice)
        args.client_style = client_config.get("baseline_style", args.client_style)
        if args.voice_config and therapist_config.get("configuration_location"):
            fixture_path = (args.voice_config.resolve().parent / therapist_config["configuration_location"]).resolve()
            fixture_data = _load_voice_config(fixture_path)
            fixture_id = therapist_config.get("voice_fixture_id")
            fixture = next(
                (item for item in fixture_data.get("fixtures", []) if item.get("id") == fixture_id),
                None,
            )
            if fixture is None:
                raise ValueError(f"Therapist voice fixture not found: {fixture_id}")
            args.therapist_alias = fixture.get("speaker_alias", args.therapist_alias)
            args.therapist_voice = fixture.get("provider_voice_reference", args.therapist_voice)
            args.therapist_style = fixture.get("baseline_style", args.therapist_style)

        script = input_path.read_text(encoding="utf-8-sig")
        script_parts = parse_parts(script)
        speakers = (args.client_alias, args.therapist_alias)
        parsed_parts = [parse_turns(part, speakers) for part in script_parts]
        print_realism_report(realism_report(parsed_parts, args.client_alias, script))
        segments = config.get("script_generation", {}).get("segments", [])

        try:
            from google import genai
            from google.oauth2 import service_account
        except ImportError as exc:
            raise RuntimeError('Gemini 3.8 TTS requires google-genai>=2.33.0. Install requirements.txt.') from exc

        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path), scopes=("https://www.googleapis.com/auth/cloud-platform",)
        )
        client = genai.Client(
            enterprise=True,
            project=args.project,
            location=args.location,
            credentials=credentials,
        )
        cache_dir = output_path.parent / f".parts_{output_path.stem}"
        cache_dir.mkdir(parents=True, exist_ok=True)
        rendered: list[tuple[wave._wave_params, bytes]] = []

        for index, turns in enumerate(parsed_parts, 1):
            part_path = cache_dir / f"part-{index:02d}.wav"
            if part_path.exists() and part_path.stat().st_size > 44:
                rendered.append(read_wave(part_path.read_bytes()))
                print(f"Part {index}/{len(parsed_parts)} loaded from cache.", flush=True)
                continue
            segment = segments[index - 1] if index <= len(segments) else {}
            client_segment = segment.get("client_direction", "")
            therapist_segment = segment.get("therapist_direction", "")
            groups: list[tuple[int, list[dict[str, str]]]] = []
            current_group: list[dict[str, str]] = []
            current_pause = 0
            for turn in turns:
                pause_seconds = int(turn.get("pause_before_seconds") or 0)
                if pause_seconds and current_group:
                    groups.append((current_pause, current_group))
                    current_group = []
                    current_pause = pause_seconds
                elif pause_seconds:
                    current_pause = pause_seconds
                current_group.append(turn)
            if current_group:
                groups.append((current_pause, current_group))

            group_audio: list[tuple[int, wave._wave_params, bytes]] = []
            for group_index, (pause_before_seconds, group_turns) in enumerate(groups, 1):
                group_path = (
                    part_path
                    if len(groups) == 1
                    else cache_dir / f"part-{index:02d}-chunk-{group_index:02d}.wav"
                )
                if group_path.exists() and group_path.stat().st_size > 44:
                    params, frames = read_wave(group_path.read_bytes())
                    group_audio.append((pause_before_seconds, params, frames))
                    print(
                        f"Part {index}/{len(parsed_parts)} chunk {group_index}/{len(groups)} loaded from cache.",
                        flush=True,
                    )
                    continue

                contents = []
                for turn in group_turns:
                    is_client = turn["speaker"] == args.client_alias
                    base = args.client_style if is_client else args.therapist_style
                    segment_style = client_segment if is_client else therapist_segment
                    if args.prompt:
                        base = f"{args.prompt}. {base}"
                    contents.append({
                        "text": turn["text"],
                        "speech_metadata": {
                            "speaker": turn["speaker"],
                            "style": _style(base, segment_style, turn["direction"]),
                        },
                    })

                print(
                    f"Synthesizing part {index}/{len(parsed_parts)} chunk {group_index}/{len(groups)}...",
                    flush=True,
                )
                for attempt in range(1, 6):
                    try:
                        response = client.models.generate_content(
                            model=args.model,
                            contents=[{"role": "user", "parts": contents}],
                            config={
                                "response_modalities": ["AUDIO"],
                                "speech_config": {
                                    "multi_speaker_voice_config": {
                                        "speaker_voice_configs": [
                                            {"speaker": args.client_alias, "voice_config": {"voice": args.client_voice}},
                                            {"speaker": args.therapist_alias, "voice_config": {"voice": args.therapist_voice}},
                                        ]
                                    }
                                },
                            },
                        )
                        audio = _audio_from_response(response)
                        group_path.write_bytes(audio)
                        params, frames = read_wave(audio)
                        group_audio.append((pause_before_seconds, params, frames))
                        break
                    except Exception as exc:
                        if attempt == 5:
                            raise
                        backoff = 4 * attempt
                        print(
                            f"Part {index} chunk {group_index} attempt {attempt} failed ({exc}); "
                            f"retrying in {backoff}s...",
                            flush=True,
                        )
                        time.sleep(backoff)

            if len(groups) > 1:
                expected_group = group_audio[0][1]
                comparable_group = (
                    expected_group.nchannels,
                    expected_group.sampwidth,
                    expected_group.framerate,
                    expected_group.comptype,
                )
                for group_index, (_, params, _) in enumerate(group_audio[1:], 2):
                    actual_group = (params.nchannels, params.sampwidth, params.framerate, params.comptype)
                    if actual_group != comparable_group:
                        raise ValueError(f"Part {index} chunk {group_index} has incompatible WAV parameters.")
                with wave.open(str(part_path), "wb") as part_output:
                    part_output.setnchannels(expected_group.nchannels)
                    part_output.setsampwidth(expected_group.sampwidth)
                    part_output.setframerate(expected_group.framerate)
                    for pause_before_seconds, _, frames in group_audio:
                        if pause_before_seconds:
                            silence_frames = int(expected_group.framerate * pause_before_seconds)
                            silence = (
                                b"\x00"
                                * silence_frames
                                * expected_group.sampwidth
                                * expected_group.nchannels
                            )
                            part_output.writeframes(silence)
                        part_output.writeframes(frames)
            rendered.append(read_wave(part_path.read_bytes()))

        expected = rendered[0][0]
        comparable = (expected.nchannels, expected.sampwidth, expected.framerate, expected.comptype)
        for index, (params, _) in enumerate(rendered[1:], 2):
            actual = (params.nchannels, params.sampwidth, params.framerate, params.comptype)
            if actual != comparable:
                raise ValueError(f"Part {index} has incompatible WAV parameters.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as output:
            output.setnchannels(expected.nchannels)
            output.setsampwidth(expected.sampwidth)
            output.setframerate(expected.framerate)
            silence = b"\x00" * int(expected.framerate * 0.45) * expected.sampwidth * expected.nchannels
            for index, (_, frames) in enumerate(rendered):
                if index:
                    output.writeframes(silence)
                output.writeframes(frames)
        print(f"Created {output_path}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
