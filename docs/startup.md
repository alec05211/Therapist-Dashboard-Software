# Startup commands

Run these commands from the repository root in PowerShell.

## Terraform, AWS HealthScribe, and RDS

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

These three commands have distinct jobs:

- `aws sso login --profile terraform` opens or refreshes the SSO session for
  the named local AWS CLI profile.
- `$env:AWS_PROFILE = "terraform"` selects that profile for the current
  PowerShell session. Terraform uses the AWS SDK rather than an `--profile`
  flag, so it needs this environment variable (or an equivalent default
  profile selection) to know which credentials to use.
- `aws sts get-caller-identity` is a read-only verification. It confirms that
  the selected profile has usable, non-expired credentials and shows which AWS
  account and IAM role Terraform will act as. It does not modify AWS resources.

You can also verify without setting the session variable by spelling out the
profile explicitly:

```powershell
aws sts get-caller-identity --profile terraform
```

The verification command should print the AWS account and an
`AWSReservedSSO_...` role ARN. Once it succeeds, Terraform can use the same
temporary credentials:

```powershell
terraform init
terraform plan
```

The AWS CLI also needs a default Region for commands such as `aws ssm` and
`aws secretsmanager`. Terraform's own `aws_region` variable does not configure
the CLI. Set the profile once (the current stack uses `us-east-1`):

```powershell
aws configure set region us-east-1 --profile terraform
```

For an explicit current-shell override, use `$env:AWS_REGION = "us-east-1"`.

Apply reviewed infrastructure changes:

```powershell
terraform apply
```

The plan now includes a private PostgreSQL RDS instance in a dedicated VPC. It
is encrypted with a customer-managed KMS key, has automated backups and
deletion protection, enforces TLS, exports operational PostgreSQL logs, and has
no public ingress. Review the plan before applying because it creates billable
AWS resources.

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

## Initialize the database after RDS is applied

The database is private by design. Run schema changes as an explicitly invoked
Fargate task inside the VPC, rather than from a laptop or through an SSM tunnel.
The task receives the RDS-managed secret directly from Secrets Manager and
connects with verified TLS. Follow [the database migration guide](../database/README.md).

## Configure Auth0 API access tokens

Create the development Auth0 API and set the same `AUTH0_AUDIENCE` value in the
root `.env` (FastAPI) and `frontend/.env.local` (Next.js). This makes the
onboarding route verify Auth0-issued RS256 access tokens server-side. Follow
[the Auth0 setup guide](AUTH0_SETUP.md) for the exact values.

## Local recorder application

Open a new PowerShell window at the repository root. Windows commonly blocks
`Activate.ps1` under its default execution policy. The following change applies
only to the current PowerShell process; it does not change the machine or your
user-level execution policy.

Start the API with this sequence:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

If you prefer not to activate the virtual environment, use its Python
executable directly. This is equivalent and does not require an execution
policy change:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn server:app --reload --port 8000
```

Start the frontend in a second PowerShell window:

```powershell
Set-Location frontend
npm run dev
```

Then open `http://localhost:3000`. The frontend uses the API address in
`frontend/.env.local` (normally `API_ORIGIN=http://127.0.0.1:8000`).

For the Terraform demo environment, prefer the startup script. It clears a
previous Python/Uvicorn process on the API port, checks whether Windows has
reserved the port (a common cause of `WinError 10013`), and binds the API to
loopback only:

```powershell
.\tools\start-demo-api.ps1
```

To use a different port, pass `-Port 8001` and set `API_ORIGIN` in
`frontend/.env.local` to `http://127.0.0.1:8001` before starting Next.js.

The API health endpoint remains available at `http://127.0.0.1:8000/healthz`.

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
