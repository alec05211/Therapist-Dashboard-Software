# Organization storage

This independent stack creates one private S3 bucket, rotating KMS key, and
HealthScribe role per organization **per environment**. It does not alter the
existing root or demo infrastructure. Buckets and keys have `prevent_destroy`;
there is no automatic record-expiration policy.

Within each bucket:

```text
clients/<client-uuid>/sessions/<session-uuid>/audio/recording.<extension>
clients/<client-uuid>/sessions/<session-uuid>/transcripts/healthscribe-transcript.json
clients/<client-uuid>/sessions/<session-uuid>/transcripts/clinical-note.json
clients/<client-uuid>/sessions/<session-uuid>/transcripts/transcript.json
therapists/<practitioner-uuid>/...   (reserved for therapist-owned files)
```

Prefixes are virtual folders, created when objects are written; empty folder
markers are unnecessary. Client records are never duplicated under therapists.
Database relationship grants control access to client records. A client's login
does not grant access to their entire folder or to clinician-only material.

HealthScribe's batch API chooses the initial result keys inside the organization
bucket; it has no `OutputKey` parameter. On completion the app saves copies under
the canonical session prefix and catalogs their S3 versions and checksums.
Original service outputs remain available for provenance.

## Provision and register

Run from the repository root with the intended AWS profile and database settings.
Use distinct working/state directories for staging and production. Never reuse
the demo database or Terraform state for another environment.

```powershell
$env:AWS_PROFILE = 'terraform'
.venv/Scripts/python.exe -m tools.configure_organization_storage --export-vars terraform/organizations/terraform.tfvars.json --environment demo
terraform '-chdir=terraform/organizations' init
terraform '-chdir=terraform/organizations' plan '-out=organization-storage.tfplan'
# Inspect the plan before applying it.
terraform '-chdir=terraform/organizations' apply organization-storage.tfplan
.venv/Scripts/python.exe -m tools.configure_organization_storage --register-from-terraform terraform/organizations
```

Registration verifies bucket ownership, public-access blocking, versioning, and
KMS encryption; applies migration 009 with checksum tracking; and inserts the
immutable organization mapping. Re-running registration is safe. Changing a
mapping requires an explicit data migration. The variables exporter retains
previous IDs so an archived organization is not accidentally removed from state.

Set `ORGANIZATION_STORAGE_ENABLED=true` in the API environment **after** successful
registration, then restart the API. The application fails closed if an enabled
organization has no registered storage. Local administrators can use existing
credentials; for a deployed API, set `application_role_name` to attach the
generated bucket-specific caller policies to its runtime role.

New organizations require this provision/register step before uploads are enabled;
web onboarding does not receive permission to create buckets or IAM roles.
Terraform state and plans are ignored by Git; retain the state securely.

## Current scope

New uploads create database sessions and artifact catalog records and use the
organization bucket. Completed recordings/transcripts can be restored from S3
if the local cache is missing. Speaker-label saves publish a new artifact version.
Existing synthetic fixtures and earlier flat-key recordings remain unchanged.

The current UI/API is still bound to the synthetic care relationship. General
client selection across organizations, migration of old artifacts, normalized
transcript-segment ingestion, and durable job workers/restart recovery remain
separate work. In-process processing can be interrupted by an API restart; the
database retains the job name and status for reconciliation. Do not resubmit a
job with an uncertain outcome without checking HealthScribe first.
