"""Permanently delete one explicitly identified client session and its artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import boto3
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database.connection import connect


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-name", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--confirm-session-id", required=True)
    args = parser.parse_args()
    if args.session_id != args.confirm_session_id:
        raise SystemExit("Confirmation session ID does not match; nothing was deleted.")

    load_dotenv(ROOT / ".env")
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT session.id, session.organization_id, session.appointment_id,
                      client.id AS client_id, client.display_name,
                      job.runtime_id, job.storage, storage.region
                 FROM app.sessions session
                 JOIN app.clients client ON client.id=session.client_id
                 LEFT JOIN app.session_storage_jobs job ON job.session_id=session.id
                 JOIN app.organization_storage storage ON storage.organization_id=session.organization_id
                WHERE session.id=%s AND lower(client.display_name)=lower(%s)""",
            (args.session_id, args.client_name),
        )
        target = cursor.fetchone()
        if not target:
            raise SystemExit("The exact client/session pair was not found; nothing was deleted.")
        cursor.execute(
            """SELECT storage_bucket, object_key, object_version_id
                 FROM app.clinical_artifacts
                WHERE session_id=%s AND lifecycle_state <> 'deleted'""",
            (args.session_id,),
        )
        artifacts = cursor.fetchall()
        expected_prefix = f"clients/{target['client_id']}/sessions/{args.session_id}/"
        if any(not row["object_key"].startswith(expected_prefix) for row in artifacts):
            raise SystemExit("An artifact is outside the expected session prefix; nothing was deleted.")

        s3 = boto3.client("s3", region_name=target["region"])
        for artifact in artifacts:
            request = {"Bucket": artifact["storage_bucket"], "Key": artifact["object_key"]}
            if artifact["object_version_id"]:
                request["VersionId"] = artifact["object_version_id"]
            s3.delete_object(**request)

        cursor.execute(
            """DELETE FROM app.client_journey_entry_revisions
                WHERE journey_entry_id IN (
                    SELECT id FROM app.client_journey_entries WHERE session_id=%s
                )""",
            (args.session_id,),
        )
        cursor.execute("DELETE FROM app.client_journey_entries WHERE session_id=%s", (args.session_id,))
        cursor.execute(
            """DELETE FROM app.longitudinal_insight_evidence
                WHERE transcript_segment_id IN (
                    SELECT segment.id FROM app.transcript_segments segment
                    JOIN app.transcript_versions version ON version.id=segment.transcript_version_id
                    WHERE version.session_id=%s
                ) OR clinical_note_version_id IN (
                    SELECT id FROM app.clinical_note_versions WHERE session_id=%s
                )""",
            (args.session_id, args.session_id),
        )
        cursor.execute("DELETE FROM app.pre_session_brief_snapshots WHERE upcoming_session_id=%s", (args.session_id,))
        cursor.execute("DELETE FROM app.longitudinal_insight_snapshots WHERE source_cutoff_session_id=%s", (args.session_id,))
        cursor.execute("DELETE FROM app.clinical_note_versions WHERE session_id=%s", (args.session_id,))
        cursor.execute("DELETE FROM app.synthesis_versions WHERE session_id=%s", (args.session_id,))
        cursor.execute(
            """DELETE FROM app.transcript_segments WHERE transcript_version_id IN (
                    SELECT id FROM app.transcript_versions WHERE session_id=%s
                )""",
            (args.session_id,),
        )
        cursor.execute("DELETE FROM app.transcript_versions WHERE session_id=%s", (args.session_id,))
        cursor.execute("DELETE FROM app.consent_records WHERE session_id=%s", (args.session_id,))
        cursor.execute("DELETE FROM app.session_practitioner_participants WHERE session_id=%s", (args.session_id,))
        cursor.execute("DELETE FROM app.session_storage_jobs WHERE session_id=%s", (args.session_id,))
        cursor.execute("DELETE FROM app.clinical_artifacts WHERE session_id=%s", (args.session_id,))
        cursor.execute("DELETE FROM app.sessions WHERE id=%s", (args.session_id,))
        if cursor.rowcount != 1:
            raise RuntimeError("Expected to delete exactly one session.")
        if target['appointment_id']:
            cursor.execute("""UPDATE app.appointments
                SET status='scheduled', updated_at=CURRENT_TIMESTAMP
                WHERE id=%s AND organization_id=%s AND client_id=%s
                  AND status='completed'""",
                (target['appointment_id'], target['organization_id'], target['client_id']))

    runtime_id = target["runtime_id"]
    cache = ROOT / "recordings" / runtime_id if runtime_id else None
    if cache and cache.is_dir() and cache.resolve().parent == (ROOT / "recordings").resolve():
        for path in sorted(cache.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        cache.rmdir()
    print(f"Deleted session {args.session_id} for {target['display_name']} and {len(artifacts)} stored artifacts.")


if __name__ == "__main__":
    main()
