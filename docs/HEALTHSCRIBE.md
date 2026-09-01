# Amazon HealthScribe: Current Implementation

> This document describes the application's present AWS HealthScribe integration. It is implementation documentation, not a long-term commitment to HealthScribe. For the product's AI/ML direction beyond this early implementation, see [AI_ML_VISION.md](AI_ML_VISION.md).

**Last updated:** 2026-09-01  
**Status:** Current early-development transcription and draft-note provider

## Purpose in this project

Amazon HealthScribe currently provides the first working version of the session-processing pipeline. It converts a recorded therapy-session audio file into:

- A timestamped transcript.
- Speaker-labeled transcript segments (diarization).
- A generated clinical-document / draft-note artifact.

It is effective enough for early development because it lets the project test the end-to-end therapist review experience before building or operating custom ML systems. HealthScribe output is always a draft for human review; it must not be treated as a clinical conclusion or final documentation without therapist review.

## What the local application does today

The local FastAPI application in `server.py` uses **asynchronous batch Medical Scribe jobs**—not the streaming API—for the browser-recorded workflow.

```text
Browser microphone recording
        |
        v
POST /transcribe (local FastAPI server)
        |
        +--> Store recording locally: recordings/<session-id>/recording.*
        |
        +--> Upload recording to private S3 input bucket
        |
        +--> Start Amazon HealthScribe batch job
        |
        v
Amazon HealthScribe
        |
        +--> Write raw transcript JSON to private S3 output bucket
        +--> Write raw clinical-document JSON to private S3 output bucket
        |
        v
Local server polls job status, downloads outputs, and stores:
        - healthscribe-transcript.json (raw transcript)
        - clinical-note.json (raw clinical document)
        - transcript.json (UI-ready transcript, segments, and note sections)
        - healthscribe-status.json (processing state)
```

The UI-ready `transcript.json` retains each transcript segment's start time, end time, text, and reported participant role. This enables the product's transcript-to-audio playback experience: a selected segment can be mapped back to the corresponding portion of the saved audio recording.

## How HealthScribe is used

### 1. Upload and job creation

When `/transcribe` receives an audio file, the server:

1. Creates a unique local session directory.
2. Saves the uploaded audio file locally.
3. Uploads it to the input S3 bucket at `recordings/<session-id>/recording.<extension>`.
4. Calls `StartMedicalScribeJob` with:
   - the input S3 URI;
   - the output bucket name;
   - the Terraform-provisioned batch data-access role;
   - `ShowSpeakerLabels: true`;
   - `MaxSpeakerLabels: 2`.

### 2. Processing and results

The server polls `GetMedicalScribeJob` until it is complete or failed. For a completed job, HealthScribe provides locations for:

- A transcript JSON document containing conversation transcript segments, timing, and participant information.
- A clinical-document JSON document containing generated summarized sections.

The application downloads both raw artifacts from S3. It then normalizes transcript segments and clinical-document sections into its own UI-ready JSON structure. Keeping the raw output alongside the normalized version makes it possible to inspect what HealthScribe returned and change the UI format without losing the source artifact.

### Current implementation constraints

- The job request currently sets a maximum of two speaker labels. Supporting sessions with more participants will require an intentional change to this configuration and UI/data-model review.
- The application reads HealthScribe's reported participant roles as provided; therapists can save local speaker-label overrides in the session transcript.
- Processing occurs after upload rather than live during a session.
- Audio files and outputs are also written to the local `recordings/` directory. That directory contains sensitive session data and requires the same care as cloud-stored artifacts.
- The Terraform configuration includes a resource-access role for streaming use, but the current local recording flow uses batch jobs.

## AWS infrastructure provisioned by Terraform

The infrastructure definition is [main.tf](../main.tf). Terraform manages the AWS resources that HealthScribe and the application need; HealthScribe jobs themselves are started dynamically by the application, not created as Terraform resources.

| Component | Why it exists | Key characteristics in the current configuration |
| --- | --- | --- |
| Input S3 bucket | Holds audio uploaded for batch processing | Private, public access blocked, ownership enforced, encrypted with the project KMS key |
| Output S3 bucket | Receives HealthScribe transcript and clinical-document artifacts | Private, public access blocked, ownership enforced, encrypted with the project KMS key |
| Customer-managed KMS key | Encrypts S3 artifacts at rest | Key rotation enabled; 30-day deletion waiting period |
| Batch data-access IAM role | Lets the HealthScribe batch service read source audio and write results | Trusted by `transcribe.amazonaws.com`; scoped to the input/output buckets and KMS key |
| Streaming resource-access IAM role | Supports potential HealthScribe streaming use | Trusted by `transcribe.streaming.amazonaws.com`; not used by today's batch workflow |
| Application caller IAM policy | Lets the application upload audio, manage jobs, read results, use KMS, and pass required roles | Must be attached to the IAM principal used by the application |

Bucket names are generated from the project name, AWS account ID, and AWS Region to stay globally unique. The default Region is `us-east-1`.

## Terraform: what it is and how it fits

Terraform is infrastructure-as-code. Instead of manually creating buckets, IAM roles, encryption keys, and policies in the AWS console, the desired infrastructure is declared in `main.tf` and Terraform calculates and applies the required changes.

The usual process is:

1. Authenticate to AWS through the configured IAM Identity Center profile.
2. Run `terraform init` to install the declared AWS provider and initialize the working directory.
3. Run `terraform plan` to preview what Terraform would create, change, or remove.
4. Review the plan carefully, especially because this application handles sensitive data.
5. Run `terraform apply` to create or update the infrastructure.
6. Retrieve Terraform outputs and configure the local application's `.env` file.

The detailed local commands and setup notes live in [startup.md](startup.md). In short:

```powershell
aws sso login --profile terraform
$env:AWS_PROFILE = "terraform"
terraform init
terraform plan
terraform apply
```

After a successful apply, use these outputs in the local `.env` file:

```powershell
terraform output -raw healthscribe_input_bucket
terraform output -raw healthscribe_output_bucket
terraform output -raw healthscribe_batch_data_access_role_arn
```

```text
AWS_REGION=us-east-1
HEALTHSCRIBE_INPUT_BUCKET=<Terraform output>
HEALTHSCRIBE_OUTPUT_BUCKET=<Terraform output>
HEALTHSCRIBE_BATCH_DATA_ACCESS_ROLE_ARN=<Terraform output>
```

The local server uses temporary AWS credentials from `AWS_PROFILE`; AWS access keys and secrets do not belong in `.env`.

## Security and operational considerations

- Do not commit `.env`, Terraform state, plan files, AWS credentials, recordings, transcripts, or clinical notes.
- Keep S3 buckets private and maintain least-privilege IAM policies.
- Before any infrastructure teardown, deliberately decide how sensitive input and output artifacts will be retained or securely deleted. Non-empty S3 buckets prevent normal Terraform deletion, and the KMS key uses a 30-day scheduled-deletion window.
- Before real-world use, establish and validate the applicable consent, privacy, retention, access-control, legal, clinical, and compliance requirements.
- Treat generated clinical documentation as therapist-reviewed draft content.

## Relationship to the long-term ML direction

HealthScribe is a practical early-development dependency, not the intended final intelligence layer. It enables rapid product learning while the project defines what a psychiatric-care-specific transcription, diarization, note-generation, and longitudinal-insight system should do—and how it should be measured, controlled, and made accountable.

See [AI_ML_VISION.md](AI_ML_VISION.md) for that direction.
