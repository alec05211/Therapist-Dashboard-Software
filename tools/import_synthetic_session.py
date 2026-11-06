"""Submit one fictional recording to the durable demo HealthScribe pipeline.

Database credentials are supplied by the runtime secret wrapper. This tool never
prints them and refuses to target a client outside Jeremy Heartwell's synthetic
demo caseload.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def configure_database(args: argparse.Namespace) -> None:
    ca_path = str(Path(args.sslrootcert).resolve()).replace("\\", "/")
    os.environ["DATABASE_URL"] = (
        f"postgresql://{quote(args.username, safe='')}:{quote(args.password, safe='')}"
        f"@{args.host}:5432/{quote(args.database, safe='')}"
        f"?sslmode=verify-full&sslrootcert={quote(ca_path, safe='/:')}"
    )
    os.environ["ORGANIZATION_STORAGE_ENABLED"] = "true"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--sslrootcert", required=True)
    parser.add_argument("--appointment-id", required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    configure_database(args)

    import boto3

    import server
    from database.connection import connect
    from database import organization_storage

    audio = args.audio.resolve()
    if audio.suffix.lower() != ".wav" or not audio.is_file():
        raise ValueError("Synthetic session audio must be an existing WAV file.")

    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT client.id AS client_id, client.organization_id,
                      actor.auth0_subject, appointment.status AS appointment_status,
                      completed.runtime_id AS completed_runtime_id
               FROM app.appointments AS appointment
               JOIN app.clients AS client ON client.id=appointment.client_id
               JOIN app.organization_practitioners AS practitioner
                 ON practitioner.id=appointment.primary_practitioner_id
               JOIN app.organization_memberships AS membership
                 ON membership.id=practitioner.membership_id
               JOIN app.application_users AS actor ON actor.id=membership.user_id
               LEFT JOIN LATERAL (
                 SELECT job.runtime_id
                 FROM app.sessions AS session
                 JOIN app.session_storage_jobs AS job ON job.session_id=session.id
                 WHERE session.appointment_id=appointment.id AND job.status='COMPLETED'
                 ORDER BY job.updated_at DESC LIMIT 1
               ) AS completed ON true
               WHERE appointment.id=%s
                 AND client.display_name='Marcus Reynolds'
                 AND practitioner.professional_name='Jeremy Heartwell'""",
            (args.appointment_id,),
        )
        context = cursor.fetchone()
    if not context:
        raise RuntimeError("The requested Marcus/Jeremy appointment is not available.")
    if context["completed_runtime_id"]:
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE app.appointments SET status='completed', updated_at=CURRENT_TIMESTAMP
                   WHERE id=%s AND status IN ('scheduled','confirmed')""",
                (args.appointment_id,),
            )
        print(json.dumps({
            "runtime_id": context["completed_runtime_id"],
            "status": "COMPLETED",
            "session_status": "review",
            "appointment_status": "completed",
            "repaired_existing": True,
        }))
        return
    if context["appointment_status"] not in {"scheduled", "confirmed"}:
        raise RuntimeError("The requested Marcus/Jeremy appointment is not available.")

    care_context = {
        "client_id": str(context["client_id"]),
        "organization_id": str(context["organization_id"]),
    }
    storage = organization_storage.create_upload(
        care_context, ".wav", context["auth0_subject"], args.appointment_id
    )
    storage["label"] = args.label
    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """UPDATE app.session_storage_jobs SET storage=%s
               WHERE runtime_id=%s""",
            (json.dumps(storage), storage["runtime_id"]),
        )

    directory = server.session_directory(storage["runtime_id"])
    directory.mkdir(parents=True, exist_ok=False)
    recording = directory / "recording.wav"
    shutil.copyfile(audio, recording)
    try:
        organization_storage.put_artifact(
            storage, recording, "audio_recording", storage["audio_key"],
            "audio/wav", "user_upload",
        )
        boto3.client("transcribe", region_name=storage["region"]).start_medical_scribe_job(
            MedicalScribeJobName=storage["job_name"],
            Media={"MediaFileUri": f"s3://{storage['bucket']}/{storage['audio_key']}"},
            OutputBucketName=storage["bucket"],
            DataAccessRoleArn=storage["healthscribe_role_arn"],
            Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": server.HEALTHSCRIBE_MAX_SPEAKERS},
            OutputEncryptionKMSKeyId=storage["kms_key_arn"],
        )
        organization_storage.set_job_status(storage, "IN_PROGRESS")
        server.process_job(
            storage["runtime_id"], storage["job_name"], storage["audio_key"], storage
        )
    except Exception:
        organization_storage.set_job_status(
            storage, "FAILED", "Synthetic session import failed."
        )
        raise

    with connect() as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT job.status, session.status AS session_status,
                      appointment.status AS appointment_status
               FROM app.session_storage_jobs AS job
               JOIN app.sessions AS session ON session.id=job.session_id
               JOIN app.appointments AS appointment ON appointment.id=session.appointment_id
               WHERE job.runtime_id=%s""",
            (storage["runtime_id"],),
        )
        result = cursor.fetchone()
    if result["status"] != "COMPLETED":
        raise RuntimeError("HealthScribe did not complete the synthetic session import.")
    if result["appointment_status"] != "completed":
        with connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """UPDATE app.appointments SET status='completed', updated_at=CURRENT_TIMESTAMP
                   WHERE id=%s AND status IN ('scheduled','confirmed')""",
                (args.appointment_id,),
            )
        result["appointment_status"] = "completed"
    print(json.dumps({"runtime_id": storage["runtime_id"], **result}, default=str))


if __name__ == "__main__":
    main()
