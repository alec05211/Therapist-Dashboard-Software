"""Create a WAV file from UTF-8 text with Gemini 3.8 TTS."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CREDENTIALS = ROOT / ".secrets" / "google_tts-script-runner_key.json"
DEFAULT_MODEL = "gemini-3.8-flash-tts"
DEFAULT_STYLE = "Read the text clearly and naturally with restrained expression."
REALISM_PREFLIGHT = """
=== REQUIRED TTS GENERATION PREFLIGHT ===
Read docs/ai/SYNTHETIC_SESSION_REALISM.md before generating session material.
Never globally slow, accelerate, interpolate, or time-stretch a recording.
If native output misses its duration target, revise the transcript or exact silence and render again.
Hesitation and vocal style are production choices, not clinical findings.
=========================================
""".strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="UTF-8 text file to synthesize")
    parser.add_argument("-o", "--output", type=Path, help="Output .wav path")
    parser.add_argument("--format", choices=("wav",), help="Gemini 3.8 unary output is WAV")
    parser.add_argument("--voice", default="Kore", help="Prebuilt, extended, designed, or replicated voice reference")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--style", "--prompt", dest="style", default=DEFAULT_STYLE)
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT"))
    parser.add_argument("--location", default="global")
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--acknowledge-realism-policy",
        action="store_true",
        help="Confirm the native-timing and synthetic-dialogue policy was read",
    )
    return parser


def _resolve_format_and_output(
    input_path: Path, output_path: Path | None, requested_format: str | None
) -> tuple[str, Path]:
    if output_path and output_path.suffix.lower() != ".wav":
        raise ValueError("Gemini 3.8 TTS output must use a .wav extension")
    if requested_format and requested_format != "wav":
        raise ValueError("Gemini 3.8 TTS output must use WAV")
    return "wav", output_path or input_path.with_suffix(".wav")


def _validate_request(text: str, style: str) -> None:
    if not text.strip():
        raise ValueError("The input text file is empty.")
    if not style.strip():
        raise ValueError("The style direction is empty.")


def _audio_from_response(response) -> bytes:
    try:
        audio = response.candidates[0].content.parts[0].inline_data.data
    except (AttributeError, IndexError, TypeError) as exc:
        raise RuntimeError("Gemini returned no audio content.") from exc
    if not audio:
        raise RuntimeError("Gemini returned empty audio content.")
    return audio


def synthesize(args: argparse.Namespace) -> Path:
    input_path = args.input.resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input text file not found: {input_path}")
    _, output_path = _resolve_format_and_output(
        input_path, args.output.resolve() if args.output else None, args.format
    )
    if output_path.exists() and not args.overwrite:
        raise FileExistsError(f"Output exists: {output_path}; pass --overwrite to replace it.")
    text = input_path.read_text(encoding="utf-8-sig")
    _validate_request(text, args.style)
    if not args.project:
        raise ValueError("Set GOOGLE_CLOUD_PROJECT or pass --project.")
    credentials_path = args.credentials.resolve()
    if not credentials_path.is_file():
        raise FileNotFoundError(f"Credential file not found: {credentials_path}")

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
    response = client.models.generate_content(
        model=args.model,
        contents=[{
            "role": "user",
            "parts": [{"text": text, "speech_metadata": {"style": args.style}}],
        }],
        config={
            "response_modalities": ["AUDIO"],
            "speech_config": {"voice_config": {"voice": args.voice}},
        },
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_audio_from_response(response))
    return output_path


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        print(REALISM_PREFLIGHT, flush=True)
        if not args.acknowledge_realism_policy:
            raise ValueError(
                "Generation is blocked until --acknowledge-realism-policy is supplied after reviewing the preflight."
            )
        output = synthesize(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Created {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
