"""Synthesize a two-speaker Gemini-TTS script and join its parts into one WAV."""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tempfile
import wave
from pathlib import Path

from google.api_core.client_options import ClientOptions
from google.cloud import texttospeech
from google.oauth2 import service_account


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CREDENTIALS = ROOT / ".secrets" / "google_tts-script-runner_key.json"
PART_HEADING = re.compile(r"(?m)^## Part \d+[^\n]*\n")
MAX_DIALOGUE_BYTES = 4_000


def parse_parts(script: str) -> list[str]:
    matches = list(PART_HEADING.finditer(script))
    if not matches:
        raise ValueError("Script must contain headings such as '## Part 1'.")
    parts: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(script)
        part = script[match.end() : end].strip()
        if part:
            parts.append(part)
    return parts


def read_wave(audio: bytes) -> tuple[wave._wave_params, bytes]:
    with wave.open(io.BytesIO(audio), "rb") as source:
        params = source.getparams()
        return params, source.readframes(source.getnframes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Dialogue script with ## Part N headings")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Final .wav path")
    parser.add_argument("--marcus-voice", default="Sadachbia")
    parser.add_argument("--jeremy-voice", default="Sadaltager")
    parser.add_argument("--model", default="gemini-2.5-flash-tts")
    parser.add_argument("--prompt", help="Override the default performance direction")
    parser.add_argument("--region", default="global")
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        input_path = args.input.resolve()
        output_path = args.output.resolve()
        credentials_path = args.credentials.resolve()
        if output_path.suffix.lower() != ".wav":
            raise ValueError("Output must use a .wav extension.")
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(f"Output exists: {output_path}; pass --overwrite to replace it.")
        if not credentials_path.is_file():
            raise FileNotFoundError(f"Credential file not found: {credentials_path}")
        credential_data = json.loads(credentials_path.read_text(encoding="utf-8"))
        if credential_data.get("type") != "service_account":
            raise ValueError("Credentials must be a service-account JSON key.")

        parts = parse_parts(input_path.read_text(encoding="utf-8-sig"))
        for index, part in enumerate(parts, 1):
            size = len(part.encode("utf-8"))
            if size > MAX_DIALOGUE_BYTES:
                raise ValueError(
                    f"Part {index} is {size:,} UTF-8 bytes; the Cloud TTS limit is "
                    f"{MAX_DIALOGUE_BYTES:,}."
                )
            if "Marcus:" not in part or "Jeremy:" not in part:
                raise ValueError(f"Part {index} must contain both Marcus: and Jeremy: turns.")

        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path), scopes=("https://www.googleapis.com/auth/cloud-platform",)
        )
        endpoint = (
            "texttospeech.googleapis.com"
            if args.region == "global"
            else f"{args.region}-texttospeech.googleapis.com"
        )
        client = texttospeech.TextToSpeechClient(
            credentials=credentials, client_options=ClientOptions(api_endpoint=endpoint)
        )
        voice_config = texttospeech.MultiSpeakerVoiceConfig(
            speaker_voice_configs=[
                texttospeech.MultispeakerPrebuiltVoice(
                    speaker_alias="Marcus", speaker_id=args.marcus_voice
                ),
                texttospeech.MultispeakerPrebuiltVoice(
                    speaker_alias="Jeremy", speaker_id=args.jeremy_voice
                ),
            ]
        )
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            model_name=args.model,
            multi_speaker_voice_config=voice_config,
        )
        default_prompt = (
            "Create a clean, close-mic studio recording of a fictional therapy conversation. "
            "Voices only: absolutely no music, ambience, room tone, hiss, or sound effects. "
            "Do not speak bracketed stage directions; perform them as silence. The conversation "
            "is slow, private, and uncertain. Leave a noticeable beat before most replies. Treat "
            "[pause] as about two seconds and [long pause] as about five seconds. Both men are "
            "actively searching for words rather than reciting polished dialogue. Marcus has a "
            "deep, low adult male voice; he is depleted and guarded, but understated, never "
            "theatrical. Jeremy has a mature, low adult male voice; he is calm and sparse, never "
            "overly soothing or emphatic. Preserve false starts, ellipses, repetitions, and "
            "self-corrections. Do not rush to the ends of sentences."
        )
        prompt = args.prompt or default_prompt

        rendered: list[tuple[wave._wave_params, bytes]] = []
        with tempfile.TemporaryDirectory(prefix="gemini-tts-dialogue-") as temporary_directory:
            temporary_path = Path(temporary_directory)
            for index, part in enumerate(parts, 1):
                print(f"Synthesizing part {index}/{len(parts)}...", flush=True)
                response = client.synthesize_speech(
                    input=texttospeech.SynthesisInput(text=part, prompt=prompt),
                    voice=voice,
                    audio_config=texttospeech.AudioConfig(
                        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                        sample_rate_hertz=24_000,
                    ),
                )
                part_path = temporary_path / f"part-{index:02d}.wav"
                part_path.write_bytes(response.audio_content)
                rendered.append(read_wave(response.audio_content))

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
