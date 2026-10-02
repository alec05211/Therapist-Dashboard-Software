from __future__ import annotations

import unittest
from pathlib import Path

from tools.google_tts import _resolve_format_and_output, _validate_request


class GoogleTtsTests(unittest.TestCase):
    def test_defaults_to_mp3_next_to_input(self) -> None:
        input_path = Path("narration.txt")
        audio_format, output_path = _resolve_format_and_output(input_path, None, None)
        self.assertEqual(audio_format, "mp3")
        self.assertEqual(output_path, Path("narration.mp3"))

    def test_infers_wav_from_output(self) -> None:
        audio_format, output_path = _resolve_format_and_output(
            Path("narration.txt"), Path("audio/result.wav"), None
        )
        self.assertEqual(audio_format, "wav")
        self.assertEqual(output_path, Path("audio/result.wav"))

    def test_rejects_mismatched_format_and_extension(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not match"):
            _resolve_format_and_output(Path("narration.txt"), Path("result.wav"), "mp3")

    def test_rejects_text_over_cloud_api_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "at most 4,000 bytes"):
            _validate_request("x" * 4_001, "Read clearly.")

    def test_accepts_utf8_text_within_limit(self) -> None:
        _validate_request("A calm café conversation.", "Read clearly.")


if __name__ == "__main__":
    unittest.main()
