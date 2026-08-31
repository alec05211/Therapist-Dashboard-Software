# Startup commands

Run these commands from the repository root in PowerShell.

## Terraform and AWS HealthScribe

Authenticate with AWS IAM Identity Center at the start of each new terminal
session, or whenever your SSO session expires:

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
uvicorn server:app --reload
```

Open `http://127.0.0.1:8000` in a browser.
