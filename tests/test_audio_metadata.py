import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave

from database.audio_metadata import recording_duration


class AudioMetadataTests(unittest.TestCase):
    def test_wav_duration_counts_all_audio_including_trailing_silence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'recording.wav'
            with wave.open(str(path), 'wb') as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(8000)
                audio.writeframes(b'\0\0' * (65 * 8000 + 4000))
            self.assertEqual(recording_duration(path), 65.5)

    def test_compressed_audio_uses_container_duration(self):
        result = subprocess.CompletedProcess([], 0, stdout=json.dumps({'format': {'duration': '125.75'}}).encode())
        with patch('database.audio_metadata.subprocess.run', return_value=result) as probe:
            self.assertEqual(recording_duration('recording.mp3'), 125.75)
        self.assertEqual(probe.call_args.kwargs['timeout'], 30)

    def test_webm_without_duration_uses_last_audio_packet_end(self):
        results = [
            subprocess.CompletedProcess([], 0, stdout=b'{"streams": [{}]}'),
            subprocess.CompletedProcess([], 0, stdout=b'{"packets": [{"pts_time": "0", "duration_time": "0.02"}, {"pts_time": "70.12", "duration_time": "0.02"}]}'),
        ]
        with patch('database.audio_metadata.subprocess.run', side_effect=results):
            self.assertAlmostEqual(recording_duration('recording.webm'), 70.14)

    def test_unreadable_audio_does_not_fabricate_a_duration(self):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired('ffprobe', 30)):
            with self.subTest(error=type(error).__name__), patch('database.audio_metadata.subprocess.run', side_effect=error):
                self.assertIsNone(recording_duration('unavailable.mp3'))


if __name__ == '__main__':
    unittest.main()
