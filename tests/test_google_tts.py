from __future__ import annotations

import unittest
from pathlib import Path

from tools.google_tts import _resolve_format_and_output, _validate_request
from tools.finalize_tts_wav import validate_duration_preserved, validate_native_duration
from tools.google_tts_dialogue import (
    REALISM_POLICY_PATH,
    REALISM_PREFLIGHT,
    parse_parts,
    parse_turns,
    realism_report,
)


class GoogleTtsTests(unittest.TestCase):
    def test_defaults_to_wav_next_to_input(self) -> None:
        input_path = Path("narration.txt")
        audio_format, output_path = _resolve_format_and_output(input_path, None, None)
        self.assertEqual(audio_format, "wav")
        self.assertEqual(output_path, Path("narration.wav"))

    def test_infers_wav_from_output(self) -> None:
        audio_format, output_path = _resolve_format_and_output(
            Path("narration.txt"), Path("audio/result.wav"), None
        )
        self.assertEqual(audio_format, "wav")
        self.assertEqual(output_path, Path("audio/result.wav"))

    def test_rejects_non_wav_extension(self) -> None:
        with self.assertRaisesRegex(ValueError, "must use a .wav"):
            _resolve_format_and_output(Path("narration.txt"), Path("result.mp3"), None)

    def test_rejects_empty_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty"):
            _validate_request("  ", "Read clearly.")

    def test_dialogue_parser_builds_structured_turns(self) -> None:
        turns = parse_turns(
            "THERAPIST: [gently] What happened?\nCLIENT: I waited. [pause] Then I called.",
            ("CLIENT", "THERAPIST"),
        )
        self.assertEqual(turns[0]["speaker"], "THERAPIST")
        self.assertEqual(turns[0]["direction"], "gently")
        self.assertIn("<short pause>", turns[1]["text"])

    def test_dialogue_parts_are_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "## Part 1"):
            parse_parts("THERAPIST: Hello")

    def test_standalone_silence_is_preserved_for_pcm_assembly(self) -> None:
        turns = parse_turns(
            "CLIENT: I need a second.\n[SILENCE - 8 SECONDS - DO NOT SPEAK]\nTHERAPIST: Take your time.",
            ("CLIENT", "THERAPIST"),
        )
        self.assertEqual(turns[1]["pause_before_seconds"], "8")
        self.assertNotIn("pause", turns[1]["text"].lower())

    def test_accepts_utf8_text_within_limit(self) -> None:
        _validate_request("A calm café conversation.", "Read clearly.")

    def test_realism_policy_requires_native_timing_and_imperfect_dialogue(self) -> None:
        policy = REALISM_POLICY_PATH.read_text(encoding="utf-8")
        self.assertIn("Never slow down, speed up, time-stretch", policy)
        self.assertIn("The client recalls conversations, chronology, and exact wording too precisely", policy)
        self.assertIn("The therapist reflects too accurately and too often", policy)
        self.assertIn("ordinary confusion, repetition, topic drift, silence", policy)
        self.assertIn("Never globally slow, accelerate, interpolate, or time-stretch", REALISM_PREFLIGHT)

    def test_realism_report_surfaces_dialogue_review_indicators(self) -> None:
        script = """## Part 1
THERAPIST: Take your time.
CLIENT: Um... wait, no, that's not right. I don't remember the exact words.
[SILENCE - 6 SECONDS - DO NOT SPEAK]
THERAPIST: What do you remember?
CLIENT: Maybe it was Tuesday.
"""
        parts = parse_parts(script)
        parsed = [parse_turns(part, ("CLIENT", "THERAPIST")) for part in parts]
        report = realism_report(parsed, "CLIENT", script)
        self.assertEqual(report["client_turns_with_explicit_disfluency"], 1)
        self.assertEqual(report["client_turns_with_uncertain_recall"], 2)
        self.assertEqual(report["exact_silence_cues"], 1)

    def test_native_duration_rejects_short_render_instead_of_stretching(self) -> None:
        with self.assertRaisesRegex(ValueError, "Do not time-stretch"):
            validate_native_duration(38 * 60, 45, 50)
        validate_native_duration(47 * 60, 45, 50)

    def test_finalization_must_preserve_duration(self) -> None:
        validate_duration_preserved(2820.0, 2820.1)
        with self.assertRaisesRegex(ValueError, "native timing must be preserved"):
            validate_duration_preserved(2820.0, 2819.0)


if __name__ == "__main__":
    unittest.main()
