# Startup commands

Run these commands from the repository root in PowerShell.

## Terraform and AWS HealthScribe

Configure the `terraform` AWS IAM Identity Center profile once on a new machine:

```powershell
aws configure sso --profile terraform
```

Use the following values when prompted:

```text
SSO session name: therapist-dashboard
SSO start URL: https://ssoins-7223d57ad843694d.portal.us-east-1.app.aws
SSO region: us-east-1
```

The session name is only a local label. Authenticate at the start of each new
terminal session, or whenever the SSO session expires:

```powershell
aws sso login --profile terraform
$env:AWS_PROFILE = "terraform"
aws sts get-caller-identity
```

The final command should print the AWS account and an `AWSReservedSSO_...` role
ARN. Once it succeeds, Terraform can use the same temporary credentials:

```powershell
terraform init
terraform plan
```

Apply reviewed infrastructure changes:

```powershell
terraform apply
```

Preview a teardown before removing infrastructure:

```powershell
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
```

Terraform will not delete a non-empty S3 bucket. Before destroying this stack,
decide whether the HealthScribe input recordings and output transcripts/clinical
notes must be retained or securely deleted, then empty both buckets if deletion
is intended. The customer-managed KMS key is scheduled for deletion after its
30-day waiting period; it is not removed immediately.

Do not commit Terraform state, plan files, AWS credentials, or `.env` files.

## Configure the local HealthScribe server

After Terraform has been applied, retrieve its three batch-job values:

```powershell
terraform output -raw healthscribe_input_bucket
terraform output -raw healthscribe_output_bucket
terraform output -raw healthscribe_batch_data_access_role_arn
```

Add their values to the local `.env` file. This file is ignored by Git and must
not be committed:

```text
AWS_REGION=us-east-1
HEALTHSCRIBE_INPUT_BUCKET=your-input-bucket-name
HEALTHSCRIBE_OUTPUT_BUCKET=your-output-bucket-name
HEALTHSCRIBE_BATCH_DATA_ACCESS_ROLE_ARN=arn:aws:iam::123456789012:role/your-batch-role
```

The server uses the temporary credentials from `AWS_PROFILE=terraform`; it does
not need an AWS access key or secret in `.env`.

## Local recorder application

Activate the local Python environment and start the development server:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

Open `http://127.0.0.1:8000` in a browser.

## Test an existing audio file

Use the local `/transcribe` endpoint to test a recording without using the
browser microphone. This follows the same workflow as the frontend: it creates
a local session folder, uploads the audio, starts the HealthScribe job, and
saves the completed artifacts locally.

With the server running on port 8000, submit a WAV file from PowerShell:

```powershell
curl.exe -X POST -F "audio=@C:\Users\avuil\Downloads\ElevenLabs_basic_sample_dialogue_1.wav" http://127.0.0.1:8000/transcribe
```

The response returns a session `id` with status `IN_PROGRESS`. Check its
progress at `http://127.0.0.1:8000/transcripts/<session-id>/status` and retrieve
the completed transcript at `http://127.0.0.1:8000/transcripts/<session-id>`.

Do not upload test files directly to the input S3 bucket as a replacement for
this request. A raw S3 upload does not create a HealthScribe job, does not
register a local session, and leaves no job identifier for the application to
poll. It is only useful for low-level AWS troubleshooting when a separate,
complete batch-job request is also issued.
