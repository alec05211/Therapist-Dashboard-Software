"""Invoke the private inference worker. The application owns access and persistence."""
import base64
import json
import logging
import os

import boto3
from botocore.config import Config
from psycopg.types.json import Json

from database.connection import connect

logger = logging.getLogger(__name__)


def enabled():
    return bool(os.environ.get("SPEAKER_MATCHER_FUNCTION"))


def invoke(event, region=None):
    response = boto3.client("lambda", region_name=region,
                            config=Config(read_timeout=190, retries={"total_max_attempts": 1})).invoke(
        FunctionName=os.environ["SPEAKER_MATCHER_FUNCTION"],
        Payload=json.dumps(event).encode(),
    )
    with response["Payload"] as payload:
        result = json.load(payload)
    if response.get("FunctionError"):
        raise RuntimeError("Speaker inference failed")
    return result


def enroll(subject, audio):
    embedding = invoke({"operation": "enroll", "audio": base64.b64encode(audio).decode()})["embedding"]
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""INSERT INTO app.account_voice_profiles(subject, embedding) VALUES (%s,%s)
            ON CONFLICT (subject) DO UPDATE SET embedding=EXCLUDED.embedding, updated_at=CURRENT_TIMESTAMP""",
            (subject, Json(embedding)))


def match_session(storage, version_id, segments):
    if not enabled():
        return
    try:
        _match_session(storage, version_id, segments)
    except Exception:
        logger.warning("Automatic speaker matching failed for transcript %s", version_id)


def _match_session(storage, version_id, segments):
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("""SELECT 'therapist' AS role, voice.id, voice.embedding, voice.updated_at
            FROM app.session_practitioner_participants participant
            JOIN app.organization_practitioners practitioner ON practitioner.id=participant.practitioner_id
            JOIN app.organization_memberships membership ON membership.id=practitioner.membership_id
            JOIN app.application_users actor ON actor.id=membership.user_id
            JOIN app.account_voice_profiles voice ON voice.subject=actor.auth0_subject
            WHERE participant.session_id=%s AND practitioner.organization_id=%s
              AND participant.participation_role='therapist'
              AND practitioner.status='active' AND membership.status='active' AND actor.status='active'
            UNION ALL
            SELECT 'client', voice.id, voice.embedding, voice.updated_at
            FROM app.client_portal_accounts portal
            JOIN app.account_voice_profiles voice ON voice.subject=portal.auth0_subject
            WHERE portal.client_id=%s AND portal.status='active'""",
            (storage["session_id"], storage["organization_id"], storage["client_id"]))
        profiles = cursor.fetchall()
        if not profiles or len({row["role"] for row in profiles}) != len(profiles):
            return
        cursor.execute("""SELECT object_version_id FROM app.clinical_artifacts
            WHERE session_id=%s AND organization_id=%s AND client_id=%s
              AND storage_bucket=%s AND object_key=%s AND artifact_type='audio_recording'
              AND lifecycle_state='active' AND deleted_at IS NULL
            ORDER BY created_at DESC LIMIT 1""",
            (storage["session_id"], storage["organization_id"], storage["client_id"],
             storage["bucket"], storage["audio_key"]))
        artifact = cursor.fetchone()
    if not artifact:
        return
    params = {"Bucket": storage["bucket"], "Key": storage["audio_key"]}
    if artifact["object_version_id"]:
        params["VersionId"] = artifact["object_version_id"]
    region = storage["region"]
    url = boto3.client("s3", region_name=region).generate_presigned_url("get_object", Params=params, ExpiresIn=300)
    references = {str(row["id"]): row for row in profiles}
    turns = [[row["speaker"], float(row["start"]), float(row["end"])]
             for row in segments if row.get("speaker")]
    logger.info("speaker_match_invoked transcript=%s profiles=%d turns=%d", version_id, len(references), len(turns))
    matches = invoke({"operation": "match", "url": url, "turns": turns,
                      "references": {key: row["embedding"] for key, row in references.items()}}, region)
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id FROM app.transcript_versions WHERE id=%s FOR UPDATE", (version_id,))
        if not cursor.fetchone():
            return
        cursor.execute("DELETE FROM app.transcript_voice_assignments WHERE transcript_version_id=%s",
                       (version_id,))
        for label, match in matches.items():
            row = references[match["profile_id"]]
            cursor.execute("""INSERT INTO app.transcript_voice_assignments
                (transcript_version_id, source_label, participant_role, profile_id)
                SELECT %s,%s,%s,id FROM app.account_voice_profiles
                WHERE id=%s AND updated_at=%s FOR SHARE
                ON CONFLICT (transcript_version_id, source_label) DO UPDATE
                SET participant_role=EXCLUDED.participant_role, profile_id=EXCLUDED.profile_id""",
                (version_id, label, row["role"], row["id"], row["updated_at"]))

    logger.info("speaker_match_persisted transcript=%s candidates=%d", version_id, len(matches))


def read_names(cursor, storage, version_id):
    from database.speaker_identification import read_defaults
    cursor.execute("""SELECT source_label, participant_role FROM app.transcript_voice_assignments
        WHERE transcript_version_id=%s""", (version_id,))
    matches = cursor.fetchall()
    defaults = read_defaults(cursor, storage) if matches else {}
    return {row["source_label"]: defaults[row["participant_role"]] for row in matches
            if defaults.get(row["participant_role"])}
