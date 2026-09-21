"""Import the synthetic Heartwell/Sadic case into organization RDS and S3 storage.

The command is intentionally idempotent. It uses stable session identifiers,
skips catalogued artifacts with matching checksums, and creates the curated
longitudinal seed only once. HealthScribe-derived journey entries remain in the
proposed state for therapist review.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from dotenv import load_dotenv
from psycopg.types.json import Json

from ai_harness.brief_projection import project_accepted_insights
from database import organization_storage, session_review
from database.connection import connect
from database.longitudinal_records import InsightEvidence, InsightItem, LongitudinalRecordRepository


ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = ROOT / "demo-data" / "heartwell-sadic-case"
INSIGHT_GENERATOR = "Curated synthetic case migration"
BRIEF_GENERATOR = "Accepted-history deterministic projection"

SESSIONS = (
    (1, "intake-and-stabilization", "2026-08-10T15:00:00-04:00"),
    (2, "noticing-the-pressure-cycle", "2026-08-17T15:00:00-04:00"),
    (3, "making-room-for-rest", "2026-08-24T15:00:00-04:00"),
    (4, "the-deadline-setback", "2026-08-31T15:00:00-04:00"),
    (5, "practicing-clear-requests", "2026-09-07T15:00:00-04:00"),
    (6, "six-session-review", "2026-09-14T15:00:00-04:00"),
)


def _session_id(number: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"therapist-dashboard/heartwell-sadic/session-{number:02d}"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _context() -> dict[str, str]:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT client.id AS client_id, client.organization_id,
                      actor.id AS actor_user_id, actor.auth0_subject,
                      practitioner.id AS practitioner_id, access.id AS access_id,
                      storage.bucket, storage.region, storage.kms_key_arn,
                      storage.healthscribe_role_arn
               FROM app.client_portal_accounts portal
               JOIN app.clients client ON client.id=portal.client_id
               JOIN app.client_therapist_access access
                 ON access.client_id=client.id AND access.organization_id=client.organization_id
               JOIN app.organization_practitioners practitioner ON practitioner.id=access.practitioner_id
               JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id
               JOIN app.application_users actor ON actor.id=membership.user_id
               JOIN app.organization_storage storage ON storage.organization_id=client.organization_id
               WHERE portal.synthetic_case_key='heartwell-sadic'
                 AND portal.status='active' AND client.status='active'
                 AND access.revoked_at IS NULL AND actor.status='active'"""
        )
        rows = cursor.fetchall()
    if len(rows) != 1:
        raise RuntimeError("Expected one active Heartwell/Sadic care relationship with organization storage.")
    return {key: str(value) for key, value in rows[0].items()}


def _storage(context: dict[str, str], number: int) -> dict[str, str]:
    session_id = _session_id(number)
    prefix = organization_storage.session_prefix(context["client_id"], session_id)
    return {
        "bucket": context["bucket"],
        "region": context["region"],
        "kms_key_arn": context["kms_key_arn"],
        "healthscribe_role_arn": context["healthscribe_role_arn"],
        "organization_id": context["organization_id"],
        "client_id": context["client_id"],
        "session_id": session_id,
        "prefix": prefix,
        "audio_key": f"{prefix}audio/recording.wav",
        "runtime_id": f"session-{session_id}",
        "job_name": f"synthetic-heartwell-sadic-{number:02d}",
        "label": f"Synthetic · Elena Sadić · Session {number:02d}",
    }


def _ensure_session(context: dict[str, str], storage: dict[str, str], started_at: datetime, ended_at: datetime) -> None:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO app.sessions
                 (id, organization_id, client_id, status, started_at, ended_at,
                  created_by_user_id, created_at, updated_at)
               VALUES (%s,%s,%s,'processing',%s,%s,%s,%s,CURRENT_TIMESTAMP)
               ON CONFLICT (id) DO UPDATE SET
                 started_at=EXCLUDED.started_at, ended_at=EXCLUDED.ended_at,
                 updated_at=CURRENT_TIMESTAMP
               WHERE app.sessions.organization_id=EXCLUDED.organization_id
                 AND app.sessions.client_id=EXCLUDED.client_id""",
            (
                storage["session_id"], context["organization_id"], context["client_id"],
                started_at, ended_at, context["actor_user_id"], started_at,
            ),
        )
        cursor.execute(
            """INSERT INTO app.session_practitioner_participants
                 (session_id, practitioner_id, client_therapist_access_id, participation_role)
               VALUES (%s,%s,%s,'therapist')
               ON CONFLICT (session_id, practitioner_id) DO NOTHING""",
            (storage["session_id"], context["practitioner_id"], context["access_id"]),
        )
        cursor.execute(
            """INSERT INTO app.session_storage_jobs
                 (runtime_id, session_id, organization_id, client_id, job_name, storage,
                  status, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,'UPLOADING',%s,CURRENT_TIMESTAMP)
               ON CONFLICT (runtime_id) DO UPDATE SET storage=EXCLUDED.storage,
                 updated_at=CURRENT_TIMESTAMP
               WHERE app.session_storage_jobs.session_id=EXCLUDED.session_id
                 AND app.session_storage_jobs.organization_id=EXCLUDED.organization_id
                 AND app.session_storage_jobs.client_id=EXCLUDED.client_id""",
            (
                storage["runtime_id"], storage["session_id"], context["organization_id"],
                context["client_id"], storage["job_name"], Json(storage), started_at,
            ),
        )


def _put_once(storage: dict[str, str], path: Path, artifact_type: str, key: str, content_type: str, source: str) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT id FROM app.clinical_artifacts
               WHERE organization_id=%s AND client_id=%s AND session_id=%s
                 AND storage_bucket=%s AND object_key=%s AND sha256_checksum=%s
                 AND lifecycle_state='active' AND deleted_at IS NULL
               ORDER BY created_at DESC LIMIT 1""",
            (
                storage["organization_id"], storage["client_id"], storage["session_id"],
                storage["bucket"], key, digest,
            ),
        )
        existing = cursor.fetchone()
    if existing:
        return str(existing["id"])
    return organization_storage.put_artifact(storage, path, artifact_type, key, content_type, source)


def _import_session(context: dict[str, str], number: int, slug: str, date_text: str) -> dict[str, int | str]:
    directory = CASE_ROOT / f"session-{number:02d}-{slug}"
    normalized = _load(directory / "transcript.json")
    raw_transcript = _load(directory / "healthscribe-transcript.json")
    raw_note = _load(directory / "clinical-note.json")
    segments = normalized.get("segments", [])
    if not segments:
        raise RuntimeError(f"Session {number:02d} has no normalized transcript segments.")
    started_at = datetime.fromisoformat(date_text)
    ended_at = started_at + timedelta(seconds=max(float(item["end"]) for item in segments))
    storage = _storage(context, number)
    _ensure_session(context, storage, started_at, ended_at)

    _put_once(storage, directory / "recording.wav", "audio_recording", storage["audio_key"], "audio/wav", "application")
    raw_id = _put_once(
        storage, directory / "healthscribe-transcript.json", "raw_transcript",
        f"{storage['prefix']}transcripts/healthscribe-transcript.json", "application/json", "healthscribe",
    )
    _put_once(
        storage, directory / "clinical-note.json", "raw_clinical_document",
        f"{storage['prefix']}transcripts/clinical-note.json", "application/json", "healthscribe",
    )
    _put_once(
        storage, directory / "transcript.json", "normalized_transcript_export",
        f"{storage['prefix']}transcripts/transcript.json", "application/json", "healthscribe",
    )
    session_review.persist_result(
        storage, segments, normalized.get("clinical_note", []), raw_id, raw_transcript, raw_note,
    )
    session_review.save_speaker_labels(storage, normalized.get("speakers", {}), context["auth0_subject"])
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("UPDATE app.transcript_versions SET created_at=%s WHERE session_id=%s", (started_at, storage["session_id"]))
        cursor.execute("UPDATE app.synthesis_versions SET created_at=%s WHERE session_id=%s", (started_at, storage["session_id"]))
        cursor.execute(
            "UPDATE app.client_journey_entries SET created_at=%s, updated_at=%s WHERE session_id=%s",
            (started_at, started_at, storage["session_id"]),
        )
    return {"session": number, "runtime_id": storage["runtime_id"], "segments": len(segments)}


def _segment_id(cursor, number: int, quote: str) -> str:
    cursor.execute(
        """SELECT segment.id
           FROM app.transcript_segments segment
           JOIN app.transcript_versions transcript ON transcript.id=segment.transcript_version_id
           WHERE transcript.session_id=%s AND segment.content=%s""",
        (_session_id(number), quote),
    )
    rows = cursor.fetchall()
    if len(rows) != 1:
        raise RuntimeError(f"Expected one source segment for Session {number:02d}: {quote[:48]}")
    return str(rows[0]["id"])


def _seed_longitudinal_records(context: dict[str, str]) -> tuple[str, str]:
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT id FROM app.longitudinal_insight_snapshots
               WHERE organization_id=%s AND client_id=%s AND generator_name=%s
               ORDER BY version_number DESC LIMIT 1""",
            (context["organization_id"], context["client_id"], INSIGHT_GENERATOR),
        )
        existing = cursor.fetchone()
        evidence = {
            "pressure_origin": _segment_id(cursor, 1, "Lately, it feels like I am either working, thinking about working, or feeling guilty that I am not working."),
            "role_history": _segment_id(cursor, 1, "My family relied on me a lot when my dad got sick last year."),
            "setback": _segment_id(cursor, 4, "I did not ask which case had priority."),
            "request": _segment_id(cursor, 5, "My heart was racing before I spoke, but I said, I can move both cases forward, and I need help deciding which one takes precedence today."),
            "help_as_debt": _segment_id(cursor, 5, "Someone helps me and then I feel like I have to repay them right away."),
            "current_shift": _segment_id(cursor, 6, "Sometimes I catch it."),
            "launch": _segment_id(cursor, 6, "I need to ask for priorities before I'm already overwhelmed."),
            "care": _segment_id(cursor, 6, "I still do not know how to let people take care of me without feeling like I owe them something."),
            "father": _segment_id(cursor, 6, "And I want to talk more about my dad because I think a lot of this started before my job got so busy."),
        }

    if existing:
        snapshot_id = str(existing["id"])
    else:
        def sources(*names: str) -> tuple[InsightEvidence, ...]:
            return tuple(InsightEvidence(transcript_segment_id=evidence[name]) for name in names)

        items = (
            InsightItem(
                item_kind="relevant_history", review_state="accepted", display_order=0,
                content={"text": "The upcoming launch and the client's own priority question."},
                evidence=sources("launch"),
            ),
            InsightItem(
                item_kind="trajectory", review_state="accepted", display_order=1,
                content={"title": "Pressure, self-criticism, and overextension", "text": "Possible pattern to review: pressure and anticipated disappointment have repeatedly been followed by overwork, reduced rest, and difficulty asking for priorities. The latest session includes an earlier recognition of that sequence."},
                evidence=sources("pressure_origin", "setback", "current_shift"),
            ),
            InsightItem(
                item_kind="trajectory", review_state="accepted", display_order=2,
                content={"title": "Direct requests as a developing practice", "text": "Across recent sessions, direct requests to a supervisor and close supports appear to be a meaningful area of practice."},
                evidence=sources("setback", "request", "launch"),
            ),
            InsightItem(
                item_kind="open_thread", review_state="accepted", display_order=3,
                content={"text": "What feels important to understand about receiving care without turning it into obligation?"},
                evidence=sources("care", "help_as_debt"),
            ),
            InsightItem(
                item_kind="open_thread", review_state="accepted", display_order=4,
                content={"text": "What connection, if any, does the client want to explore between current pressure and the experience of the father's illness?"},
                evidence=sources("father", "role_history"),
            ),
            InsightItem(
                item_kind="open_thread", review_state="accepted", display_order=5,
                content={"text": "How is the approaching launch affecting the client's ability to use the priority question before pressure escalates?"},
                evidence=sources("launch", "request"),
            ),
        )
        with connect() as connection:
            repository = LongitudinalRecordRepository(connection)
            snapshot_id = repository.create_insight_snapshot(
                organization_id=context["organization_id"], client_id=context["client_id"],
                content={
                    "text": "Across six sessions, the record describes a recurring pressure cycle involving anticipated disappointment, increased self-demand, and less room for rest or support. Recent sessions also show the client practicing more direct requests and sometimes recognizing the cycle earlier. The links between responsibility, care, and family experience remain important but unresolved.",
                    "review_note": "Curated synthetic baseline migrated with source-linked transcript evidence.",
                },
                items=items, generator_name=INSIGHT_GENERATOR, generator_version="1",
                selection_policy_version="synthetic-baseline-v1", actor_user_id=context["actor_user_id"],
                status="accepted", source_cutoff_session_id=_session_id(6),
            )
            with connection.cursor() as cursor:
                cursor.execute(
                    """UPDATE app.longitudinal_insight_snapshots
                       SET reviewed_by_user_id=%s, reviewed_at=CURRENT_TIMESTAMP WHERE id=%s""",
                    (context["actor_user_id"], snapshot_id),
                )

    with connect() as connection:
        repository = LongitudinalRecordRepository(connection)
        packet = repository.build_pre_session_context_packet(
            organization_id=context["organization_id"], client_id=context["client_id"],
        )
        if packet is None:
            raise RuntimeError("The accepted synthetic insight snapshot did not produce a context packet.")
        content = project_accepted_insights(packet, [])
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT id FROM app.pre_session_brief_snapshots
                   WHERE organization_id=%s AND client_id=%s AND source_insight_snapshot_id=%s
                     AND generator_name=%s ORDER BY created_at DESC LIMIT 1""",
                (context["organization_id"], context["client_id"], snapshot_id, BRIEF_GENERATOR),
            )
            brief = cursor.fetchone()
        brief_id = str(brief["id"]) if brief else repository.create_pre_session_brief_snapshot(
            organization_id=context["organization_id"], client_id=context["client_id"],
            context_packet=packet, content=content, generator_name=BRIEF_GENERATOR,
            generator_version="1", status="draft", source_insight_snapshot_id=snapshot_id,
            actor_user_id=context["actor_user_id"],
        )
    return snapshot_id, brief_id


def main() -> None:
    load_dotenv(ROOT / ".env", override=True)
    context = _context()
    imported = [_import_session(context, *session) for session in SESSIONS]
    snapshot_id, brief_id = _seed_longitudinal_records(context)
    print(json.dumps({
        "sessions": imported,
        "insight_snapshot_id": snapshot_id,
        "pre_session_brief_snapshot_id": brief_id,
    }, indent=2))


if __name__ == "__main__":
    main()
