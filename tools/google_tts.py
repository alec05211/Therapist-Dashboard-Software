"""Create an MP3 or WAV file from a UTF-8 text file with Gemini-TTS."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CREDENTIALS = ROOT / ".secrets" / "google_tts-script-runner_key.json"
DEFAULT_MODEL = "gemini-2.5-flash-tts"
DEFAULT_PROMPT = "Read the following text clearly and naturally."
MAX_FIELD_BYTES = 4_000
MAX_REQUEST_BYTES = 8_000


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a UTF-8 text file to speech with Google Cloud Gemini-TTS."
    )
    parser.add_argument("input", type=Path, help="UTF-8 text file to synthesize")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output .mp3 or .wav path (default: input name with the selected extension)",
    )
    parser.add_argument(
        "--format",
        choices=("mp3", "wav"),
        help="Audio format; inferred from --output, or MP3 when neither is supplied",
    )
    parser.add_argument("--voice", default="Kore", help="Gemini-TTS voice (default: Kore)")
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"Gemini-TTS model (default: {DEFAULT_MODEL})"
    )
    parser.add_argument("--language", default="en-US", help="BCP-47 language code (default: en-US)")
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Natural-language delivery/style instructions",
    )
    parser.add_argument(
        "--region",
        default="global",
        help="Cloud TTS region, such as global, us, or eu (default: global)",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=DEFAULT_CREDENTIALS,
        help=f"Service-account JSON path (default: {DEFAULT_CREDENTIALS})",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output file")
    return parser


def _resolve_format_and_output(
    input_path: Path, output_path: Path | None, requested_format: str | None
) -> tuple[str, Path]:
    output_suffix = output_path.suffix.lower() if output_path else ""
    suffix_format = {".mp3": "mp3", ".wav": "wav"}.get(output_suffix)
    if output_path and not suffix_format:
        raise ValueError("--output must end in .mp3 or .wav")
    if requested_format and suffix_format and requested_format != suffix_format:
        raise ValueError("--format does not match the --output file extension")
    audio_format = requested_format or suffix_format or "mp3"
    return audio_format, output_path or input_path.with_suffix(f".{audio_format}")


def _validate_request(text: str, prompt: str) -> None:
    if not text.strip():
        raise ValueError("The input text file is empty.")
    text_bytes = len(text.encode("utf-8"))
    prompt_bytes = len(prompt.encode("utf-8"))
    if text_bytes > MAX_FIELD_BYTES:
        raise ValueError(
            f"Input text is {text_bytes:,} UTF-8 bytes; Gemini-TTS Cloud API allows "
            f"at most {MAX_FIELD_BYTES:,} bytes in one text request. Split the source file."
        )
    if prompt_bytes > MAX_FIELD_BYTES:
        raise ValueError(
            f"The prompt is {prompt_bytes:,} UTF-8 bytes; the limit is {MAX_FIELD_BYTES:,}."
        )
    if text_bytes + prompt_bytes > MAX_REQUEST_BYTES:
        raise ValueError(
            f"Text plus prompt is {text_bytes + prompt_bytes:,} UTF-8 bytes; "
            f"the combined limit is {MAX_REQUEST_BYTES:,}."
        )


def _validate_service_account(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Credential file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Credential file is not valid UTF-8 JSON: {path}") from exc
    if payload.get("type") != "service_account":
        raise ValueError(
            "The credential file must be a Google Cloud service-account JSON key."
        )


def synthesize(args: argparse.Namespace) -> Path:
    input_path = args.input.resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input text file not found: {input_path}")

    audio_format, output_path = _resolve_format_and_output(
        input_path, args.output.resolve() if args.output else None, args.format
    )
    if output_path.exists() and not args.overwrite:
        raise FileExistsError(
            f"Output file already exists: {output_path} (pass --overwrite to replace it)"
        )

    try:
        text = input_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Input must be a UTF-8 text file: {input_path}") from exc
    _validate_request(text, args.prompt)

    credentials_path = args.credentials.expanduser().resolve()
    _validate_service_account(credentials_path)

    try:
        from google.api_core.client_options import ClientOptions
        from google.cloud import texttospeech
        from google.oauth2 import service_account
    except ImportError as exc:
        raise RuntimeError(
            "Google Cloud TTS support is not installed. Run: "
            "python -m pip install -r requirements.txt"
        ) from exc

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
    synthesis_input = texttospeech.SynthesisInput(text=text, prompt=args.prompt)
    voice = texttospeech.VoiceSelectionParams(
        language_code=args.language,
        name=args.voice,
        model_name=args.model,
    )
    encoding = (
        texttospeech.AudioEncoding.MP3
        if audio_format == "mp3"
        else texttospeech.AudioEncoding.LINEAR16
    )
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=texttospeech.AudioConfig(audio_encoding=encoding),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(response.audio_content)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        output_path = synthesize(args)
    except Exception as exc:  # Present command-line failures without a noisy traceback.
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Created {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
