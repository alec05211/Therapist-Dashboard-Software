"""Local recorder server backed by Amazon HealthScribe batch jobs."""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urlparse
from uuid import uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Body, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from psycopg import Error as PsycopgError
from psycopg.types.json import Json

from database.auth import validate_access_token
from database.connection import connect
from pydantic import BaseModel, Field

app = FastAPI()
load_dotenv(Path(__file__).with_name(".env"))
RECORDINGS_DIRECTORY = Path(__file__).with_name("recordings")
SYNTHETIC_TRANSCRIPT = Path(__file__).with_name("synthetic_conversation.json")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
INPUT_BUCKET = os.getenv("HEALTHSCRIBE_INPUT_BUCKET")
OUTPUT_BUCKET = os.getenv("HEALTHSCRIBE_OUTPUT_BUCKET")
BATCH_ROLE_ARN = os.getenv("HEALTHSCRIBE_BATCH_DATA_ACCESS_ROLE_ARN")
POLL_SECONDS = max(1, int(os.getenv("HEALTHSCRIBE_POLL_SECONDS", "5")))


class TherapistOnboardingRequest(BaseModel):
    organization_name: str = Field(min_length=1, max_length=200)
    professional_name: str = Field(min_length=1, max_length=200)
    practice_type: Literal["solo", "group"]
    team_setup: Literal["later", "now"]


@app.get("/healthz")
def healthz():
    """Process health check; deliberately does not disclose dependencies."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    """Readiness check for private operational validation."""
    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except (RuntimeError, PsycopgError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The service is not ready.",
        ) from exc
    return {"status": "ready"}


def configuration() -> tuple[str, str, str]:
    missing = [name for name, value in {
        "HEALTHSCRIBE_INPUT_BUCKET": INPUT_BUCKET,
        "HEALTHSCRIBE_OUTPUT_BUCKET": OUTPUT_BUCKET,
        "HEALTHSCRIBE_BATCH_DATA_ACCESS_ROLE_ARN": BATCH_ROLE_ARN,
    }.items() if not value]
    if missing:
        raise RuntimeError(f"Missing HealthScribe configuration: {', '.join(missing)}")
    return INPUT_BUCKET or "", OUTPUT_BUCKET or "", BATCH_ROLE_ARN or ""


def session_directory(session_id: str) -> Path:
    return RECORDINGS_DIRECTORY / Path(session_id).name


def transcript_path(session_id: str) -> Path:
    return session_directory(session_id) / "transcript.json"


def status_path(session_id: str) -> Path:
    return session_directory(session_id) / "healthscribe-status.json"


def write_json(path: Path, content: dict[str, Any]) -> None:
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")


@app.post("/onboarding/therapist", status_code=status.HTTP_201_CREATED)
def onboard_therapist(
    request: TherapistOnboardingRequest,
    authorization: str | None = Header(default=None),
):
    """Create the first organization and owner-practitioner membership."""
    claims = validate_access_token(authorization)
    auth0_subject = claims["sub"]

    try:
        with connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO app.application_users (auth0_subject, display_name)
                    VALUES (%s, %s)
                    ON CONFLICT (auth0_subject) DO UPDATE
                      SET display_name = EXCLUDED.display_name,
                          updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                    """,
                    (auth0_subject, request.professional_name.strip()),
                )
                user = cursor.fetchone()
                if not user:
                    raise RuntimeError("Could not create the application user.")

                cursor.execute(
                    """
                    SELECT membership.organization_id, organization.name
                    FROM app.organization_memberships AS membership
                    JOIN app.organizations AS organization
                      ON organization.id = membership.organization_id
                    WHERE membership.user_id = %s
                      AND membership.role = 'owner'
                      AND membership.status = 'active'
                    ORDER BY membership.created_at
                    LIMIT 1
                    """,
                    (user["id"],),
                )
                existing = cursor.fetchone()
                if existing:
                    return {
                        "created": False,
                        "organization_id": str(existing["organization_id"]),
                        "organization_name": existing["name"],
                    }

                cursor.execute(
                    """
                    INSERT INTO app.organizations (name, settings)
                    VALUES (%s, %s)
                    RETURNING id, name
                    """,
                    (
                        request.organization_name.strip(),
                        Json({
                            "practice_type": request.practice_type,
                            "team_setup": request.team_setup,
                        }),
                    ),
                )
                organization = cursor.fetchone()
                if not organization:
                    raise RuntimeError("Could not create the organization.")

                cursor.execute(
                    """
                    INSERT INTO app.organization_memberships (
                      organization_id, user_id, role, status
                    )
                    VALUES (%s, %s, 'owner', 'active')
                    RETURNING id
                    """,
                    (organization["id"], user["id"]),
                )
                membership = cursor.fetchone()
                if not membership:
                    raise RuntimeError("Could not create the organization membership.")

                cursor.execute(
                    """
                    INSERT INTO app.organization_practitioners (
                      organization_id, membership_id, professional_name, status
                    )
                    VALUES (%s, %s, %s, 'active')
                    RETURNING id
                    """,
                    (
                        organization["id"],
                        membership["id"],
                        request.professional_name.strip(),
                    ),
                )
                practitioner = cursor.fetchone()
                if not practitioner:
                    raise RuntimeError("Could not create the practitioner profile.")

                cursor.execute(
                    """
                    INSERT INTO app.audit_events (
                      organization_id, actor_user_id, action, target_type,
                      target_id, outcome, metadata
                    )
                    VALUES (%s, %s, 'organization.created', 'organization', %s,
                            'allowed', %s)
                    """,
                    (
                        organization["id"],
                        user["id"],
                        organization["id"],
                        Json({
                            "practice_type": request.practice_type,
                            "team_setup": request.team_setup,
                            "practitioner_id": str(practitioner["id"]),
                        }),
                    ),
                )

            connection.commit()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PsycopgError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The database is temporarily unavailable.",
        ) from exc

    return {
        "created": True,
        "organization_id": str(organization["id"]),
        "organization_name": organization["name"],
        "membership_id": str(membership["id"]),
        "practitioner_id": str(practitioner["id"]),
    }


def s3_location(uri: str) -> tuple[str, str]:
    """Resolve both S3 URIs and the HTTPS output URLs returned by HealthScribe."""
    parsed = urlparse(uri)
    if parsed.scheme == "s3":
        bucket_and_key = parsed.path.lstrip("/").split("/", 1)
        bucket = parsed.netloc
    elif parsed.scheme == "https":
        path_parts = parsed.path.lstrip("/").split("/", 1)
        # Virtual-hosted style: https://bucket.s3.region.amazonaws.com/key
        if ".s3." in parsed.netloc or ".s3-" in parsed.netloc:
            bucket = parsed.netloc.split(".s3", 1)[0]
            bucket_and_key = path_parts
        # Path style: https://s3.region.amazonaws.com/bucket/key
        else:
            bucket_and_key = path_parts
            bucket = bucket_and_key.pop(0) if bucket_and_key else ""
    else:
        raise ValueError("HealthScribe returned an invalid output location.")
    if not bucket or not bucket_and_key or not bucket_and_key[0]:
        raise ValueError("HealthScribe returned an invalid S3 output location.")
    return bucket, unquote(bucket_and_key[0])


def segments_from_healthscribe(document: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for segment in document.get("Conversation", {}).get("TranscriptSegments", []):
        text = str(segment.get("Content", "")).strip()
        if not text:
            continue
        role = segment.get("ParticipantDetails", {}).get("ParticipantRole")
        result.append({
            "start": float(segment.get("BeginAudioTime", 0)),
            "end": float(segment.get("EndAudioTime", 0)),
            "text": text,
            **({"speaker": role} if role else {}),
        })
    return result


def summary_from_healthscribe(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": str(section.get("SectionName", "Clinical note")).replace("_", " ").title(),
            "items": [item["SummarizedSegment"] for item in section.get("Summary", []) if item.get("SummarizedSegment")],
        }
        for section in document.get("ClinicalDocumentation", {}).get("Sections", [])
        if section.get("Summary")
    ]


def process_job(session_id: str, job_name: str, input_key: str) -> None:
    """Download completed HealthScribe JSON files to the local session folder."""
    directory = session_directory(session_id)
    try:
        input_bucket, _, _ = configuration()
        transcribe = boto3.client("transcribe", region_name=AWS_REGION)
        s3 = boto3.client("s3", region_name=AWS_REGION)
        while True:
            job = transcribe.get_medical_scribe_job(MedicalScribeJobName=job_name)["MedicalScribeJob"]
            state = job["MedicalScribeJobStatus"]
            if state in {"COMPLETED", "FAILED"}:
                break
            write_json(status_path(session_id), {"id": session_id, "status": state, "job_name": job_name})
            time.sleep(POLL_SECONDS)
        if state == "FAILED":
            raise RuntimeError(job.get("FailureReason", "HealthScribe did not complete the job."))

        outputs = job["MedicalScribeOutput"]
        transcript_bucket, transcript_key = s3_location(outputs["TranscriptFileUri"])
        note_bucket, note_key = s3_location(outputs["ClinicalDocumentUri"])
        raw_transcript = json.loads(s3.get_object(Bucket=transcript_bucket, Key=transcript_key)["Body"].read())
        raw_note = json.loads(s3.get_object(Bucket=note_bucket, Key=note_key)["Body"].read())
        write_json(directory / "healthscribe-transcript.json", raw_transcript)
        write_json(directory / "clinical-note.json", raw_note)
        segments = segments_from_healthscribe(raw_transcript)
        recording = next(directory.glob("recording.*"))
        write_json(transcript_path(session_id), {
            "id": session_id,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "audio": {"file": recording.name, "mime_type": "audio/webm"},
            "speakers": {},
            "text": " ".join(segment["text"] for segment in segments),
            "segments": segments,
            "clinical_note": summary_from_healthscribe(raw_note),
            "healthscribe": {
                "job_name": job_name,
                "input_uri": f"s3://{input_bucket}/{input_key}",
                "transcript_uri": outputs["TranscriptFileUri"],
                "clinical_note_uri": outputs["ClinicalDocumentUri"],
            },
        })
        write_json(status_path(session_id), {"id": session_id, "status": "COMPLETED", "job_name": job_name})
    except (BotoCoreError, ClientError, KeyError, OSError, ValueError, RuntimeError) as exc:
        write_json(status_path(session_id), {"id": session_id, "status": "FAILED", "job_name": job_name, "detail": str(exc)})


@app.get("/")
def page():
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/recordings/{session_id}/{filename}")
def session_recording(session_id: str, filename: str):
    path = session_directory(session_id) / Path(filename).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Recording not found.")
    return FileResponse(path, media_type="audio/webm", filename=path.name)


@app.get("/transcripts")
def transcripts():
    items = []
    for path in RECORDINGS_DIRECTORY.glob("*/transcript.json") if RECORDINGS_DIRECTORY.exists() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append({"id": path.parent.name, "label": path.parent.name, "text": data.get("text", ""), "created_at": data.get("created_at", "")})
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(items, key=lambda item: item["created_at"], reverse=True)


@app.get("/transcripts/{session_id}")
def transcript(session_id: str):
    if session_id == "synthetic":
        return json.loads(SYNTHETIC_TRANSCRIPT.read_text(encoding="utf-8"))
    path = transcript_path(session_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Transcript not found.")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["recording_url"] = f"/recordings/{session_id}/{data['audio']['file']}"
    return data


@app.get("/transcripts/{session_id}/status")
def job_status(session_id: str):
    path = status_path(session_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Processing status not found.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.put("/transcripts/{session_id}/speakers")
def save_speaker_labels(session_id: str, labels: dict[str, str] = Body(...)):
    path = transcript_path(session_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Transcript not found.")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["speakers"] = {key.strip(): value.strip() for key, value in labels.items() if key.strip() and value.strip()}
    write_json(path, data)
    return {"speakers": data["speakers"]}


@app.post("/transcribe", status_code=202)
async def transcribe(background_tasks: BackgroundTasks, audio: UploadFile = File(...)):
    try:
        input_bucket, output_bucket, data_role = configuration()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    session_id = f"session-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    job_name = f"healthscribe-{datetime.now():%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
    directory = session_directory(session_id)
    input_key = f"recordings/{session_id}/recording{suffix}"
    try:
        directory.mkdir(parents=True)
        recording = directory / f"recording{suffix}"
        recording.write_bytes(await audio.read())
        boto3.client("s3", region_name=AWS_REGION).upload_file(str(recording), input_bucket, input_key)
        boto3.client("transcribe", region_name=AWS_REGION).start_medical_scribe_job(
            MedicalScribeJobName=job_name,
            Media={"MediaFileUri": f"s3://{input_bucket}/{input_key}"},
            OutputBucketName=output_bucket,
            DataAccessRoleArn=data_role,
            Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2},
        )
        write_json(status_path(session_id), {"id": session_id, "status": "IN_PROGRESS", "job_name": job_name})
        background_tasks.add_task(process_job, session_id, job_name, input_key)
        return {"id": session_id, "status": "IN_PROGRESS"}
    except (BotoCoreError, ClientError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not start HealthScribe job: {exc}") from exc
