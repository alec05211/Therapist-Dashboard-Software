"""Regenerate still-proposed evidence guidance for one confirmed synthetic session."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from psycopg.types.json import Json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from ai_harness.journey_proposals import ANALYZER_VERSION, generate_openai_proposal_analysis
from database import client_journey
from database.connection import connect
from database.longitudinal_records import LongitudinalRecordRepository


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-name", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--confirm-session-id", required=True)
    args = parser.parse_args()
    if args.session_id != args.confirm_session_id:
        raise SystemExit("Confirmation session ID does not match; nothing was regenerated.")

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("JOURNEY_PROPOSAL_MODEL") or os.getenv("PRE_SESSION_MODEL")
    if not api_key or not model:
        raise SystemExit("OPENAI_API_KEY and JOURNEY_PROPOSAL_MODEL or PRE_SESSION_MODEL are required.")

    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT session.id, session.organization_id, session.client_id,
                      client.display_name, job.runtime_id, portal.synthetic_case_key
                 FROM app.sessions session
                 JOIN app.clients client ON client.id=session.client_id
                 JOIN app.session_storage_jobs job ON job.session_id=session.id
                 LEFT JOIN app.client_portal_accounts portal
                   ON portal.client_id=client.id AND portal.status='active'
                WHERE session.id=%s AND lower(client.display_name)=lower(%s)""",
            (args.session_id, args.client_name),
        )
        target = cursor.fetchone()
        if not target:
            raise SystemExit("The exact client/session pair was not found; nothing was regenerated.")
        if not target["synthetic_case_key"]:
            raise SystemExit("The client is not explicitly marked synthetic; nothing was sent to a model.")
        packet = LongitudinalRecordRepository(connection).build_pre_session_context_packet(
            organization_id=str(target["organization_id"]), client_id=str(target["client_id"]), limit=12)

    session_directory = (ROOT / "recordings" / target["runtime_id"]).resolve()
    if session_directory.parent != (ROOT / "recordings").resolve():
        raise SystemExit("The session cache is outside the recordings directory.")
    raw_transcript = json.loads((session_directory / "healthscribe-transcript.json").read_text(encoding="utf-8"))
    raw_note = json.loads((session_directory / "clinical-note.json").read_text(encoding="utf-8"))
    candidates = client_journey.extract_healthscribe_candidates(raw_transcript, raw_note)
    analyses, metadata = generate_openai_proposal_analysis(
        proposals=candidates, insights_context=packet, api_key=api_key, model=model)

    updated = 0
    with connect() as connection, connection.cursor() as cursor:
        for candidate in candidates:
            analysis = analyses[candidate["proposal_key"]]
            categories = [value for value in client_journey.CATEGORY_ORDER
                          if value in set(analysis["categories"])]
            proposal_analysis = {
                "source_summary": candidate["source_summary"],
                "section_name": candidate["section_name"],
                "analysis_status": "generated",
                "relationship": analysis["relationship"],
                "related_insight_item_ids": analysis["related_insight_item_ids"],
            }
            cursor.execute(
                """UPDATE app.client_journey_entries
                      SET category=%s, categories=%s, content=%s,
                          source_insight_snapshot_id=%s,
                          proposal_generator_name='OpenAI journey proposal analyzer',
                          proposal_generator_version=%s, proposal_analysis=%s,
                          updated_at=CURRENT_TIMESTAMP
                    WHERE session_id=%s AND source_summary_key=%s AND status='proposed'""",
                (categories[0], categories, analysis["synthesis_focus"],
                 packet["snapshot_id"] if packet else None,
                 f"{ANALYZER_VERSION}:{metadata['model']}", Json(proposal_analysis),
                 args.session_id, candidate["proposal_key"]),
            )
            updated += cursor.rowcount

    print(f"Regenerated {updated} proposed evidence claims for session {args.session_id}.")


if __name__ == "__main__":
    main()
