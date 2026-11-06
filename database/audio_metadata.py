"""Read recording length locally, including silence after the final utterance."""

import json
import math
from pathlib import Path
import subprocess
import wave


def recording_duration(path):
    path = Path(path)
    try:
        with wave.open(str(path), 'rb') as recording:
            return recording.getnframes() / recording.getframerate()
    except (wave.Error, EOFError, OSError):
        pass
    try:
        def probe(entries):
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-select_streams', 'a:0',
                 '-show_entries', entries, '-of', 'json', str(path.resolve())],
                capture_output=True, check=True, timeout=30,
            )
            return json.loads(result.stdout)

        metadata = probe('format=duration:stream=duration')
        durations = [metadata.get('format', {}).get('duration')]
        durations.extend(stream.get('duration') for stream in metadata.get('streams', []))
        for value in durations:
            try:
                duration = float(value)
            except (ValueError, TypeError):
                continue
            if math.isfinite(duration) and duration > 0:
                return duration
        # MediaRecorder WebM files may have no container/stream duration.
        packets = probe('packet=pts_time,duration_time').get('packets', [])
        duration = max((float(packet['pts_time']) + float(packet.get('duration_time', 0))
                        for packet in packets if 'pts_time' in packet), default=0)
        return duration if math.isfinite(duration) and duration > 0 else None
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
        return None
