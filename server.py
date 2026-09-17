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
from ai_harness.pre_session import build_pre_session_synthesis_request, generate_openai_pre_session_brief
from pydantic import BaseModel, Field

app = FastAPI()
load_dotenv(Path(__file__).with_name(".env"))
RECORDINGS_DIRECTORY = Path(__file__).with_name("recordings")
DEMO_DATA_DIRECTORY = Path(__file__).with_name("demo-data")
DEMO_SESSION_ONE_RELATIVE_DIRECTORY = Path("demo-data") / "heartwell-sadic-case" / "session-01-intake-and-stabilization"
DEMO_SESSION_ONE_DIRECTORY = Path(__file__).parent / DEMO_SESSION_ONE_RELATIVE_DIRECTORY
DEMO_SESSION_ONE_RECORDING = DEMO_SESSION_ONE_DIRECTORY / "recording.wav"
DEMO_SESSION_ONE_STATUS = DEMO_SESSION_ONE_DIRECTORY / "healthscribe-status.json"
DEMO_SESSION_ONE_ID = "heartwell-sadic-session-01"
DEMO_SESSION_ONE_TRANSCRIPT = DEMO_SESSION_ONE_DIRECTORY / "transcript.json"
DEMO_SESSION_TWO_RELATIVE_DIRECTORY = Path("demo-data") / "heartwell-sadic-case" / "session-02-noticing-the-pressure-cycle"
DEMO_SESSION_TWO_DIRECTORY = Path(__file__).parent / DEMO_SESSION_TWO_RELATIVE_DIRECTORY
DEMO_SESSION_TWO_RECORDING = DEMO_SESSION_TWO_DIRECTORY / "recording.wav"
DEMO_SESSION_TWO_STATUS = DEMO_SESSION_TWO_DIRECTORY / "healthscribe-status.json"
DEMO_SESSION_TWO_ID = "heartwell-sadic-session-02"
DEMO_SESSION_TWO_TRANSCRIPT = DEMO_SESSION_TWO_DIRECTORY / "transcript.json"
DEMO_SESSION_SLUGS = {
    3: "making-room-for-rest",
    4: "the-deadline-setback",
    5: "practicing-clear-requests",
    6: "six-session-review",
}
DEMO_SESSION_LABELS = {
    3: "Synthetic · Elena Sadić · Session 03",
    4: "Synthetic · Elena Sadić · Session 04",
    5: "Synthetic · Elena Sadić · Session 05",
    6: "Synthetic · Elena Sadić · Session 06",
}
MAX_DEMO_AUDIO_BYTES = 100 * 1024 * 1024
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


def is_demo_session_one(session_id: str) -> bool:
    return session_id == DEMO_SESSION_ONE_ID


def is_demo_session_two(session_id: str) -> bool:
    return session_id == DEMO_SESSION_TWO_ID


def demo_session_assets(session_id: str) -> tuple[Path, Path, Path] | None:
    if is_demo_session_one(session_id):
        return DEMO_SESSION_ONE_RECORDING, DEMO_SESSION_ONE_STATUS, DEMO_SESSION_ONE_TRANSCRIPT
    if is_demo_session_two(session_id):
        return DEMO_SESSION_TWO_RECORDING, DEMO_SESSION_TWO_STATUS, DEMO_SESSION_TWO_TRANSCRIPT
    session_number = additional_demo_session_number(session_id)
    if session_number is not None:
        recording, job_status, transcript, _, _ = additional_demo_session_assets(session_number)
        return recording, job_status, transcript
    return None


def additional_demo_session_assets(session_number: int) -> tuple[Path, Path, Path, str, str]:
    """Return the data-closet paths and UI metadata for Sessions 03 through 06."""
    slug = DEMO_SESSION_SLUGS.get(session_number)
    label = DEMO_SESSION_LABELS.get(session_number)
    if not slug or not label:
        raise HTTPException(status_code=404, detail="Unknown synthetic demo session.")
    directory = DEMO_DATA_DIRECTORY / "heartwell-sadic-case" / f"session-{session_number:02d}-{slug}"
    return (
        directory / "recording.wav",
        directory / "healthscribe-status.json",
        directory / "transcript.json",
        f"heartwell-sadic-session-{session_number:02d}",
        label,
    )


def additional_demo_session_number(session_id: str) -> int | None:
    for session_number in DEMO_SESSION_SLUGS:
        if session_id == f"heartwell-sadic-session-{session_number:02d}":
            return session_number
    return None


def demo_brief_evidence(session_id: str, segment_text: str) -> dict[str, Any]:
    """Resolve a deliberately selected synthetic-demo citation to a transcript segment.

    This is the first deterministic evidence-retrieval seam for the harness demo.
    It does not infer clinical meaning or call a model; production retrieval will
    replace the selected text with versioned, authorized memory-item sources.
    """
    assets = demo_session_assets(session_id)
    if assets is None:
        raise HTTPException(status_code=404, detail="Unknown synthetic demo session.")
    transcript = json.loads(assets[2].read_text(encoding="utf-8"))
    for index, segment in enumerate(transcript.get("segments", [])):
        if segment.get("text", "").strip() == segment_text:
            return {
                "evidence_id": f"{session_id}:segment:{index}",
                "session_id": session_id,
                "session_label": DEMO_SESSION_LABELS.get(additional_demo_session_number(session_id) or 0, "Synthetic · Elena Sadić"),
                "segment_index": index,
                "start": segment["start"],
                "end": segment["end"],
                "quote": segment["text"].strip(),
            }
    raise RuntimeError(f"Synthetic demo evidence was not found for {session_id}.")


@app.get("/demo/heartwell-sadic/pre-session-brief")
def demo_pre_session_brief():
    """Return a cited, deterministic pre-session brief for synthetic demo data only.

    This proves the harness contract—bounded sections, selected evidence, and
    citations—without sending data to an external model or making clinical
    inferences. It is not a production clinical brief generator.
    """
    session_id = "heartwell-sadic-session-06"
    return {
        "status": "DEMO DRAFT · deterministic evidence selection",
        "review_note": "Review the cited source before relying on any item. This demo does not assess diagnosis, risk, or treatment.",
        "sections": [
            {
                "title": "Since last session",
                "items": [{
                    "text": "A project launch is approaching; the client identified asking for priorities early as an important part of their plan.",
                    "sources": [demo_brief_evidence(session_id, "I need to ask for priorities before I'm already overwhelmed.")],
                }],
            },
            {
                "title": "Important trajectory",
                "items": [{
                    "text": "Possible pattern to consider: the client described noticing the pressure sequence sooner and sometimes interrupting it.",
                    "sources": [demo_brief_evidence(session_id, "Sometimes I catch it.")],
                }],
            },
            {
                "title": "Open loops",
                "items": [
                    {
                        "text": "The client identified difficulty receiving care without feeling indebted.",
                        "sources": [demo_brief_evidence(session_id, "I still do not know how to let people take care of me without feeling like I owe them something.")],
                    },
                    {
                        "text": "The client asked to explore the relationship with their father further.",
                        "sources": [demo_brief_evidence(session_id, "And I want to talk more about my dad because I think a lot of this started before my job got so busy.")],
                    },
                ],
            },
        ],
    }


@app.get("/demo/heartwell-sadic/pre-session-brief/request")
def demo_pre_session_synthesis_request():
    """Expose the model-ready synthetic bundle without contacting a provider."""
    brief = demo_pre_session_brief()
    evidence = [source for section in brief["sections"] for item in section["items"] for source in item["sources"]]
    return build_pre_session_synthesis_request(
        client_reference="synthetic-heartwell-sadic-client",
        evidence=evidence,
    )


@app.post("/demo/heartwell-sadic/pre-session-brief/generate")
def generate_demo_pre_session_brief():
    """Generate a synthetic-only, cited draft through the configured OpenAI key."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="OPENAI_API_KEY is not configured.")
    deterministic_brief = demo_pre_session_brief()
    evidence = [source for section in deterministic_brief["sections"] for item in section["items"] for source in item["sources"]]
    synthesis_request = build_pre_session_synthesis_request(
        client_reference="synthetic-heartwell-sadic-client",
        evidence=evidence,
    )
    try:
        generated, metadata = generate_openai_pre_session_brief(
            synthesis_request=synthesis_request,
            api_key=api_key,
            model=os.getenv("OPENAI_PRE_SESSION_MODEL", "gpt-5-mini"),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    sources_by_id = {source["evidence_id"]: source for source in evidence}
    return {
        "status": f"OPENAI DRAFT · {metadata['model']}",
        "review_note": "Synthetic demo only. Review cited sources before relying on an item; this draft does not assess diagnosis, risk, or treatment.",
        "sections": [
            {
                "title": section["title"],
                "items": [
                    {"text": item["text"], "sources": [sources_by_id[evidence_id] for evidence_id in item["evidence_ids"]]}
                    for item in section["items"]
                ],
            }
            for section in generated["sections"]
        ],
        "generation": metadata,
    }


def write_json(path: Path, content: dict[str, Any]) -> None:
    path.write_text(json.dumps(content, indent=2), encoding="utf-8")


@app.post("/demo/heartwell-sadic/session-01/audio", status_code=status.HTTP_201_CREATED)
async def upload_demo_session_one_audio(audio: UploadFile = File(...)):
    """Store one explicitly synthetic WAV file in the versioned demo-data closet.

    This intentionally does not start a HealthScribe job or write to the normal
    runtime recordings directory. It exists solely to stage Elena and Jeremy's
    first synthetic session before it is submitted through the normal pipeline.
    """
    filename = audio.filename or ""
    if Path(filename).suffix.lower() != ".wav":
        raise HTTPException(status_code=415, detail="The session-one demo upload must be a WAV file.")
    if DEMO_SESSION_ONE_RECORDING.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session-one demo recording already exists. Remove it deliberately before replacing it.",
        )

    contents = await audio.read(MAX_DEMO_AUDIO_BYTES + 1)
    if len(contents) > MAX_DEMO_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="The demo recording exceeds the 100 MB limit.")
    if len(contents) < 12 or contents[:4] != b"RIFF" or contents[8:12] != b"WAVE":
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid WAV container.")

    try:
        DEMO_SESSION_ONE_DIRECTORY.mkdir(parents=True, exist_ok=True)
        DEMO_SESSION_ONE_RECORDING.write_bytes(contents)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not store the demo recording.") from exc

    return {
        "stored": True,
        "session": "heartwell-sadic/session-01",
        "path": str(DEMO_SESSION_ONE_RELATIVE_DIRECTORY / "recording.wav"),
        "bytes": len(contents),
    }


def process_demo_session_one_job(job_name: str, input_key: str) -> None:
    """Persist HealthScribe artifacts beside the explicitly synthetic source WAV."""
    try:
        input_bucket, _, _ = configuration()
        transcribe = boto3.client("transcribe", region_name=AWS_REGION)
        s3 = boto3.client("s3", region_name=AWS_REGION)
        while True:
            job = transcribe.get_medical_scribe_job(MedicalScribeJobName=job_name)["MedicalScribeJob"]
            state = job["MedicalScribeJobStatus"]
            if state in {"COMPLETED", "FAILED"}:
                break
            write_json(DEMO_SESSION_ONE_STATUS, {"id": DEMO_SESSION_ONE_ID, "status": state, "job_name": job_name})
            time.sleep(POLL_SECONDS)
        if state == "FAILED":
            raise RuntimeError(job.get("FailureReason", "HealthScribe did not complete the job."))

        outputs = job["MedicalScribeOutput"]
        transcript_bucket, transcript_key = s3_location(outputs["TranscriptFileUri"])
        note_bucket, note_key = s3_location(outputs["ClinicalDocumentUri"])
        raw_transcript = json.loads(s3.get_object(Bucket=transcript_bucket, Key=transcript_key)["Body"].read())
        raw_note = json.loads(s3.get_object(Bucket=note_bucket, Key=note_key)["Body"].read())
        write_json(DEMO_SESSION_ONE_DIRECTORY / "healthscribe-transcript.json", raw_transcript)
        write_json(DEMO_SESSION_ONE_DIRECTORY / "clinical-note.json", raw_note)
        segments = segments_from_healthscribe(raw_transcript)
        write_json(DEMO_SESSION_ONE_DIRECTORY / "transcript.json", {
            "id": DEMO_SESSION_ONE_ID,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "audio": {"file": DEMO_SESSION_ONE_RECORDING.name, "mime_type": "audio/wav"},
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
        write_json(DEMO_SESSION_ONE_STATUS, {"id": DEMO_SESSION_ONE_ID, "status": "COMPLETED", "job_name": job_name})
    except (BotoCoreError, ClientError, KeyError, OSError, ValueError, RuntimeError) as exc:
        write_json(DEMO_SESSION_ONE_STATUS, {"id": DEMO_SESSION_ONE_ID, "status": "FAILED", "job_name": job_name, "detail": str(exc)})


@app.post("/demo/heartwell-sadic/session-01/process", status_code=status.HTTP_202_ACCEPTED)
def process_demo_session_one(background_tasks: BackgroundTasks):
    """Submit the staged synthetic Session 01 WAV to HealthScribe for processing."""
    if not DEMO_SESSION_ONE_RECORDING.is_file():
        raise HTTPException(status_code=404, detail="Upload the Session 01 demo WAV before processing it.")
    if DEMO_SESSION_ONE_STATUS.is_file():
        try:
            previous_status = json.loads(DEMO_SESSION_ONE_STATUS.read_text(encoding="utf-8")).get("status")
        except (OSError, json.JSONDecodeError):
            previous_status = None
        if previous_status in {"IN_PROGRESS", "COMPLETED"}:
            raise HTTPException(status_code=409, detail=f"Session 01 HealthScribe processing is already {previous_status.lower()}.")
    try:
        input_bucket, output_bucket, data_role = configuration()
        job_name = f"healthscribe-demo-{datetime.now():%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
        input_key = "demo-data/heartwell-sadic/session-01/recording.wav"
        boto3.client("s3", region_name=AWS_REGION).upload_file(str(DEMO_SESSION_ONE_RECORDING), input_bucket, input_key)
        boto3.client("transcribe", region_name=AWS_REGION).start_medical_scribe_job(
            MedicalScribeJobName=job_name,
            Media={"MediaFileUri": f"s3://{input_bucket}/{input_key}"},
            OutputBucketName=output_bucket,
            DataAccessRoleArn=data_role,
            Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2},
        )
        write_json(DEMO_SESSION_ONE_STATUS, {"id": DEMO_SESSION_ONE_ID, "status": "IN_PROGRESS", "job_name": job_name})
        background_tasks.add_task(process_demo_session_one_job, job_name, input_key)
        return {"id": DEMO_SESSION_ONE_ID, "status": "IN_PROGRESS", "job_name": job_name}
    except (BotoCoreError, ClientError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not start the Session 01 HealthScribe job: {exc}") from exc


@app.post("/demo/heartwell-sadic/session-02/audio", status_code=status.HTTP_201_CREATED)
async def upload_demo_session_two_audio(audio: UploadFile = File(...)):
    """Store the explicitly synthetic Session 02 WAV with its demo case artifacts."""
    filename = audio.filename or ""
    if Path(filename).suffix.lower() != ".wav":
        raise HTTPException(status_code=415, detail="The session-two demo upload must be a WAV file.")
    if DEMO_SESSION_TWO_RECORDING.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A session-two demo recording already exists. Remove it deliberately before replacing it.",
        )

    contents = await audio.read(MAX_DEMO_AUDIO_BYTES + 1)
    if len(contents) > MAX_DEMO_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="The demo recording exceeds the 100 MB limit.")
    if len(contents) < 12 or contents[:4] != b"RIFF" or contents[8:12] != b"WAVE":
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid WAV container.")

    try:
        DEMO_SESSION_TWO_DIRECTORY.mkdir(parents=True, exist_ok=True)
        DEMO_SESSION_TWO_RECORDING.write_bytes(contents)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not store the demo recording.") from exc

    return {
        "stored": True,
        "session": "heartwell-sadic/session-02",
        "path": str(DEMO_SESSION_TWO_RELATIVE_DIRECTORY / "recording.wav"),
        "bytes": len(contents),
    }


def process_demo_session_two_job(job_name: str, input_key: str) -> None:
    """Persist Session 02 HealthScribe output beside its synthetic source WAV."""
    try:
        input_bucket, _, _ = configuration()
        transcribe = boto3.client("transcribe", region_name=AWS_REGION)
        s3 = boto3.client("s3", region_name=AWS_REGION)
        while True:
            job = transcribe.get_medical_scribe_job(MedicalScribeJobName=job_name)["MedicalScribeJob"]
            state = job["MedicalScribeJobStatus"]
            if state in {"COMPLETED", "FAILED"}:
                break
            write_json(DEMO_SESSION_TWO_STATUS, {"id": DEMO_SESSION_TWO_ID, "status": state, "job_name": job_name})
            time.sleep(POLL_SECONDS)
        if state == "FAILED":
            raise RuntimeError(job.get("FailureReason", "HealthScribe did not complete the job."))

        outputs = job["MedicalScribeOutput"]
        transcript_bucket, transcript_key = s3_location(outputs["TranscriptFileUri"])
        note_bucket, note_key = s3_location(outputs["ClinicalDocumentUri"])
        raw_transcript = json.loads(s3.get_object(Bucket=transcript_bucket, Key=transcript_key)["Body"].read())
        raw_note = json.loads(s3.get_object(Bucket=note_bucket, Key=note_key)["Body"].read())
        write_json(DEMO_SESSION_TWO_DIRECTORY / "healthscribe-transcript.json", raw_transcript)
        write_json(DEMO_SESSION_TWO_DIRECTORY / "clinical-note.json", raw_note)
        segments = segments_from_healthscribe(raw_transcript)
        write_json(DEMO_SESSION_TWO_TRANSCRIPT, {
            "id": DEMO_SESSION_TWO_ID,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "audio": {"file": DEMO_SESSION_TWO_RECORDING.name, "mime_type": "audio/wav"},
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
        write_json(DEMO_SESSION_TWO_STATUS, {"id": DEMO_SESSION_TWO_ID, "status": "COMPLETED", "job_name": job_name})
    except (BotoCoreError, ClientError, KeyError, OSError, ValueError, RuntimeError) as exc:
        write_json(DEMO_SESSION_TWO_STATUS, {"id": DEMO_SESSION_TWO_ID, "status": "FAILED", "job_name": job_name, "detail": str(exc)})


@app.post("/demo/heartwell-sadic/session-02/process", status_code=status.HTTP_202_ACCEPTED)
def process_demo_session_two(background_tasks: BackgroundTasks):
    """Submit the staged synthetic Session 02 WAV to HealthScribe for processing."""
    if not DEMO_SESSION_TWO_RECORDING.is_file():
        raise HTTPException(status_code=404, detail="Upload the Session 02 demo WAV before processing it.")
    if DEMO_SESSION_TWO_STATUS.is_file():
        try:
            previous_status = json.loads(DEMO_SESSION_TWO_STATUS.read_text(encoding="utf-8")).get("status")
        except (OSError, json.JSONDecodeError):
            previous_status = None
        if previous_status == "IN_PROGRESS":
            job_name = json.loads(DEMO_SESSION_TWO_STATUS.read_text(encoding="utf-8"))["job_name"]
            input_key = "demo-data/heartwell-sadic/session-02/recording.wav"
            background_tasks.add_task(process_demo_session_two_job, job_name, input_key)
            return {"id": DEMO_SESSION_TWO_ID, "status": "IN_PROGRESS", "job_name": job_name}
        if previous_status == "COMPLETED":
            raise HTTPException(status_code=409, detail="Session 02 HealthScribe processing is already completed.")
    try:
        input_bucket, output_bucket, data_role = configuration()
        job_name = f"healthscribe-demo-{datetime.now():%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
        input_key = "demo-data/heartwell-sadic/session-02/recording.wav"
        boto3.client("s3", region_name=AWS_REGION).upload_file(str(DEMO_SESSION_TWO_RECORDING), input_bucket, input_key)
        boto3.client("transcribe", region_name=AWS_REGION).start_medical_scribe_job(
            MedicalScribeJobName=job_name,
            Media={"MediaFileUri": f"s3://{input_bucket}/{input_key}"},
            OutputBucketName=output_bucket,
            DataAccessRoleArn=data_role,
            Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2},
        )
        write_json(DEMO_SESSION_TWO_STATUS, {"id": DEMO_SESSION_TWO_ID, "status": "IN_PROGRESS", "job_name": job_name})
        background_tasks.add_task(process_demo_session_two_job, job_name, input_key)
        return {"id": DEMO_SESSION_TWO_ID, "status": "IN_PROGRESS", "job_name": job_name}
    except (BotoCoreError, ClientError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not start the Session 02 HealthScribe job: {exc}") from exc


@app.post("/demo/heartwell-sadic/session-{session_number}/audio", status_code=status.HTTP_201_CREATED)
async def upload_additional_demo_audio(session_number: int, audio: UploadFile = File(...)):
    """Stage a synthetic Session 03–06 WAV without using runtime recordings."""
    recording, _, _, _, _ = additional_demo_session_assets(session_number)
    if Path(audio.filename or "").suffix.lower() != ".wav":
        raise HTTPException(status_code=415, detail="The synthetic demo upload must be a WAV file.")
    if recording.exists():
        raise HTTPException(status_code=409, detail="A demo recording already exists. Remove it deliberately before replacing it.")
    contents = await audio.read(MAX_DEMO_AUDIO_BYTES + 1)
    if len(contents) > MAX_DEMO_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="The demo recording exceeds the 100 MB limit.")
    if len(contents) < 12 or contents[:4] != b"RIFF" or contents[8:12] != b"WAVE":
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid WAV container.")
    try:
        recording.parent.mkdir(parents=True, exist_ok=True)
        recording.write_bytes(contents)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not store the demo recording.") from exc
    return {"stored": True, "session": f"heartwell-sadic/session-{session_number:02d}", "path": str(recording.relative_to(Path(__file__).parent)), "bytes": len(contents)}


def process_additional_demo_session_job(session_number: int, job_name: str, input_key: str) -> None:
    """Download and normalize HealthScribe artifacts for synthetic Sessions 03–06."""
    recording, job_status, transcript_path, session_id, _ = additional_demo_session_assets(session_number)
    try:
        input_bucket, _, _ = configuration()
        transcribe = boto3.client("transcribe", region_name=AWS_REGION)
        s3 = boto3.client("s3", region_name=AWS_REGION)
        while True:
            job = transcribe.get_medical_scribe_job(MedicalScribeJobName=job_name)["MedicalScribeJob"]
            state = job["MedicalScribeJobStatus"]
            if state in {"COMPLETED", "FAILED"}:
                break
            write_json(job_status, {"id": session_id, "status": state, "job_name": job_name})
            time.sleep(POLL_SECONDS)
        if state == "FAILED":
            raise RuntimeError(job.get("FailureReason", "HealthScribe did not complete the job."))
        outputs = job["MedicalScribeOutput"]
        transcript_bucket, transcript_key = s3_location(outputs["TranscriptFileUri"])
        note_bucket, note_key = s3_location(outputs["ClinicalDocumentUri"])
        raw_transcript = json.loads(s3.get_object(Bucket=transcript_bucket, Key=transcript_key)["Body"].read())
        raw_note = json.loads(s3.get_object(Bucket=note_bucket, Key=note_key)["Body"].read())
        write_json(recording.parent / "healthscribe-transcript.json", raw_transcript)
        write_json(recording.parent / "clinical-note.json", raw_note)
        segments = segments_from_healthscribe(raw_transcript)
        write_json(transcript_path, {
            "id": session_id,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "audio": {"file": recording.name, "mime_type": "audio/wav"},
            "speakers": {},
            "text": " ".join(segment["text"] for segment in segments),
            "segments": segments,
            "clinical_note": summary_from_healthscribe(raw_note),
            "healthscribe": {"job_name": job_name, "input_uri": f"s3://{input_bucket}/{input_key}", "transcript_uri": outputs["TranscriptFileUri"], "clinical_note_uri": outputs["ClinicalDocumentUri"]},
        })
        write_json(job_status, {"id": session_id, "status": "COMPLETED", "job_name": job_name})
    except (BotoCoreError, ClientError, KeyError, OSError, ValueError, RuntimeError) as exc:
        write_json(job_status, {"id": session_id, "status": "FAILED", "job_name": job_name, "detail": str(exc)})


@app.post("/demo/heartwell-sadic/session-{session_number}/process", status_code=status.HTTP_202_ACCEPTED)
def process_additional_demo_session(session_number: int, background_tasks: BackgroundTasks):
    """Submit or resume one staged synthetic Session 03–06 HealthScribe job."""
    recording, job_status, _, session_id, _ = additional_demo_session_assets(session_number)
    if not recording.is_file():
        raise HTTPException(status_code=404, detail="Upload the synthetic session WAV before processing it.")
    input_key = f"demo-data/heartwell-sadic/session-{session_number:02d}/recording.wav"
    if job_status.is_file():
        try:
            previous = json.loads(job_status.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
        if previous.get("status") == "IN_PROGRESS" and previous.get("job_name"):
            background_tasks.add_task(process_additional_demo_session_job, session_number, previous["job_name"], input_key)
            return {"id": session_id, "status": "IN_PROGRESS", "job_name": previous["job_name"]}
        if previous.get("status") == "COMPLETED":
            raise HTTPException(status_code=409, detail="HealthScribe processing is already completed for this synthetic session.")
    try:
        input_bucket, output_bucket, data_role = configuration()
        job_name = f"healthscribe-demo-{datetime.now():%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
        boto3.client("s3", region_name=AWS_REGION).upload_file(str(recording), input_bucket, input_key)
        boto3.client("transcribe", region_name=AWS_REGION).start_medical_scribe_job(
            MedicalScribeJobName=job_name, Media={"MediaFileUri": f"s3://{input_bucket}/{input_key}"}, OutputBucketName=output_bucket, DataAccessRoleArn=data_role, Settings={"ShowSpeakerLabels": True, "MaxSpeakerLabels": 2},
        )
        write_json(job_status, {"id": session_id, "status": "IN_PROGRESS", "job_name": job_name})
        background_tasks.add_task(process_additional_demo_session_job, session_number, job_name, input_key)
        return {"id": session_id, "status": "IN_PROGRESS", "job_name": job_name}
    except (BotoCoreError, ClientError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not start the synthetic HealthScribe job: {exc}") from exc


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


@app.get("/demo/heartwell-sadic/session-01/recording")
def demo_session_one_recording():
    """Serve the synthetic Session 01 WAV for existing transcript playback UI."""
    if not DEMO_SESSION_ONE_RECORDING.is_file():
        raise HTTPException(status_code=404, detail="Session 01 demo recording not found.")
    return FileResponse(DEMO_SESSION_ONE_RECORDING, media_type="audio/wav", filename=DEMO_SESSION_ONE_RECORDING.name)


@app.get("/demo/heartwell-sadic/session-02/recording")
def demo_session_two_recording():
    """Serve the synthetic Session 02 WAV for existing transcript playback UI."""
    if not DEMO_SESSION_TWO_RECORDING.is_file():
        raise HTTPException(status_code=404, detail="Session 02 demo recording not found.")
    return FileResponse(DEMO_SESSION_TWO_RECORDING, media_type="audio/wav", filename=DEMO_SESSION_TWO_RECORDING.name)


@app.get("/demo/heartwell-sadic/session-{session_number}/recording")
def additional_demo_session_recording(session_number: int):
    """Serve a synthetic Session 03–06 WAV for transcript playback."""
    recording, _, _, _, _ = additional_demo_session_assets(session_number)
    if not recording.is_file():
        raise HTTPException(status_code=404, detail="Synthetic demo recording not found.")
    return FileResponse(recording, media_type="audio/wav", filename=recording.name)


@app.get("/transcripts")
def transcripts():
    items = []
    for path in RECORDINGS_DIRECTORY.glob("*/transcript.json") if RECORDINGS_DIRECTORY.exists() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append({"id": path.parent.name, "label": path.parent.name, "text": data.get("text", ""), "created_at": data.get("created_at", "")})
        except (OSError, json.JSONDecodeError):
            continue
    if DEMO_SESSION_ONE_TRANSCRIPT.is_file():
        try:
            data = json.loads(DEMO_SESSION_ONE_TRANSCRIPT.read_text(encoding="utf-8"))
            items.append({
                "id": DEMO_SESSION_ONE_ID,
                "label": "Synthetic · Elena Sadić · Session 01",
                "text": data.get("text", ""),
                "created_at": data.get("created_at", ""),
            })
        except (OSError, json.JSONDecodeError):
            pass
    if DEMO_SESSION_TWO_TRANSCRIPT.is_file():
        try:
            data = json.loads(DEMO_SESSION_TWO_TRANSCRIPT.read_text(encoding="utf-8"))
            items.append({
                "id": DEMO_SESSION_TWO_ID,
                "label": "Synthetic · Elena Sadić · Session 02",
                "text": data.get("text", ""),
                "created_at": data.get("created_at", ""),
            })
        except (OSError, json.JSONDecodeError):
            pass
    for session_number in DEMO_SESSION_SLUGS:
        _, _, path, session_id, label = additional_demo_session_assets(session_number)
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append({"id": session_id, "label": label, "text": data.get("text", ""), "created_at": data.get("created_at", "")})
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(items, key=lambda item: item["created_at"], reverse=True)


@app.get("/transcripts/{session_id}")
def transcript(session_id: str):
    demo_assets = demo_session_assets(session_id)
    path = demo_assets[2] if demo_assets else transcript_path(session_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Transcript not found.")
    data = json.loads(path.read_text(encoding="utf-8"))
    additional_number = additional_demo_session_number(session_id)
    if is_demo_session_one(session_id):
        data["recording_url"] = "/demo/heartwell-sadic/session-01/recording"
    elif is_demo_session_two(session_id):
        data["recording_url"] = "/demo/heartwell-sadic/session-02/recording"
    elif additional_number is not None:
        data["recording_url"] = f"/demo/heartwell-sadic/session-{additional_number:02d}/recording"
    else:
        data["recording_url"] = f"/recordings/{session_id}/{data['audio']['file']}"
    return data


@app.get("/transcripts/{session_id}/status")
def job_status(session_id: str):
    demo_assets = demo_session_assets(session_id)
    path = demo_assets[1] if demo_assets else status_path(session_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Processing status not found.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.put("/transcripts/{session_id}/speakers")
def save_speaker_labels(session_id: str, labels: dict[str, str] = Body(...)):
    demo_assets = demo_session_assets(session_id)
    path = demo_assets[2] if demo_assets else transcript_path(session_id)
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
