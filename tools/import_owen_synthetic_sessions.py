"""Import all twelve rendered Owen Park sessions through the durable HealthScribe path."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--sslrootcert", required=True)
    args = parser.parse_args()
    importer = ROOT / "tools" / "import_synthetic_session.py"
    audio_root = ROOT / "recordings" / "synthetic-owen-flash"
    for number in range(1, 13):
        audio = audio_root / f"session-{number:02d}.wav"
        if not audio.is_file() or audio.stat().st_size <= 44:
            raise RuntimeError(f"Missing rendered Owen audio: {audio}")
        appointment_id = uuid5(NAMESPACE_URL, f"therapist-dashboard/owen-park/session-{number:02d}")
        print(f"Importing Owen session {number:02d}/12.", flush=True)
        subprocess.run(
            [
                sys.executable, str(importer),
                "--host", args.host, "--database", args.database,
                "--username", args.username, "--password", args.password,
                "--sslrootcert", args.sslrootcert,
                "--appointment-id", str(appointment_id),
                "--audio", str(audio),
                "--label", f"Synthetic · Owen Park · Session {number:02d}",
                "--client-name", "Owen Park",
            ],
            cwd=ROOT,
            check=True,
        )
        print(f"Imported Owen session {number:02d}/12.", flush=True)
    print("All Owen sessions imported.", flush=True)


if __name__ == "__main__":
    main()
