"""Finalize a native-speed TTS WAV without changing its duration or pitch.

This tool intentionally supports sample-rate/encoding conversion only. If the
provider render misses the requested duration range, revise the transcript or
assembled silence and render again. Never use whole-file tempo manipulation.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import wave
from pathlib import Path


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as source:
        return source.getnframes() / source.getframerate()


def validate_native_duration(duration_seconds: float, minimum_minutes: float, maximum_minutes: float) -> None:
    minimum_seconds = minimum_minutes * 60
    maximum_seconds = maximum_minutes * 60
    if not minimum_seconds <= duration_seconds <= maximum_seconds:
        raise ValueError(
            f"Native render is {duration_seconds / 60:.2f} minutes; required range is "
            f"{minimum_minutes:.2f}-{maximum_minutes:.2f} minutes. Do not time-stretch it. "
            "Revise the transcript or exact assembled silence, then render again."
        )


def validate_duration_preserved(before_seconds: float, after_seconds: float, tolerance_seconds: float = 0.25) -> None:
    difference = abs(before_seconds - after_seconds)
    if difference > tolerance_seconds:
        raise ValueError(
            f"Finalization changed duration by {difference:.3f} seconds. "
            "The output is rejected because native timing must be preserved."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Native-speed provider WAV")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Final PCM WAV")
    parser.add_argument("--sample-rate", type=int, default=16000)
    parser.add_argument("--minimum-minutes", type=float, default=45.0)
    parser.add_argument("--maximum-minutes", type=float, default=50.0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        input_path = args.input.resolve()
        output_path = args.output.resolve()
        if input_path == output_path:
            raise ValueError("Input and output must be different paths.")
        if not input_path.is_file():
            raise FileNotFoundError(input_path)
        if output_path.suffix.lower() != ".wav":
            raise ValueError("Output must use a .wav extension.")
        if output_path.exists() and not args.overwrite:
            raise FileExistsError(f"Output exists: {output_path}; pass --overwrite to replace it.")

        before_seconds = wav_duration_seconds(input_path)
        validate_native_duration(before_seconds, args.minimum_minutes, args.maximum_minutes)

        try:
            import imageio_ffmpeg
        except ImportError as exc:
            raise RuntimeError("Install imageio-ffmpeg from requirements.txt.") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = output_path.with_name(f".{output_path.stem}.native-finalize.tmp.wav")
        if temporary_path.exists():
            temporary_path.unlink()
        command = [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-ar",
            str(args.sample_rate),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(temporary_path),
        ]
        subprocess.run(command, check=True)
        after_seconds = wav_duration_seconds(temporary_path)
        validate_duration_preserved(before_seconds, after_seconds)
        temporary_path.replace(output_path)
        print(
            f"Created {output_path} at native timing: {after_seconds / 60:.2f} minutes, "
            f"{args.sample_rate} Hz mono PCM."
        )
        return 0
    except Exception as exc:
        try:
            if "temporary_path" in locals() and temporary_path.exists():
                temporary_path.unlink()
        except OSError:
            pass
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
