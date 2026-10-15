"""Run the durable clinical-synthesis worker without serving HTTP traffic."""
from __future__ import annotations

import argparse
import time

from dotenv import load_dotenv

from database.clinical_synthesis_worker import process_one


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process at most one due revision.")
    parser.add_argument("--poll-seconds", type=float, default=5.0)
    args = parser.parse_args()
    if args.poll_seconds < 1 or args.poll_seconds > 60:
        raise SystemExit("--poll-seconds must be between 1 and 60.")
    load_dotenv(override=False)
    while True:
        processed = process_one()
        if args.once:
            return
        if not processed:
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()
