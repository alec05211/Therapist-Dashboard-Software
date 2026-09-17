# Disposable RDS demonstration stack

This is a separate **mock-data-only** Terraform root for demonstrating the same
PostgreSQL schema, Auth0 onboarding flow, private S3 artifact buckets, and
HealthScribe batch-job model used by the application. It does not modify the
private, production-oriented Terraform stack in the repository root.

The database is intentionally publicly addressable so a locally running FastAPI
server can reach it. It is still protected by TLS, encryption at rest, a
managed RDS secret, and a security group that admits exactly one required
operator CIDR. It will not accept `0.0.0.0/0`.

Do not put real client, recording, transcript, or other clinical data in this
environment. Public reachability is a demo convenience, not a production
security boundary.

## What it creates

- One small, single-AZ PostgreSQL RDS instance with the repository's existing
  migrations.
- Two private, encrypted S3 buckets: HealthScribe input audio and output
  artifacts. Mock artifacts expire automatically after the configured period.
- The least-privilege HealthScribe batch role and a caller policy for the
  local FastAPI process.
- A public VPC/database subnet arrangement, internet gateway, and an RDS
  security group restricted to `demo_allowed_cidr`.

It deliberately does **not** create NAT gateways, interface VPC endpoints,
Fargate, an ALB, or a domain. Those are the recurring-cost pieces of a hosted,
private production topology.

## Deploy and migrate

1. Sign in to AWS and set the intended profile and region.
2. Copy `terraform.tfvars.example` to `terraform.tfvars`; replace the example
   address with your present public IP plus `/32`.
3. From this directory, run `terraform init`, `terraform plan`, then review and
   run `terraform apply`.
4. Download the current RDS CA bundle and retrieve the managed RDS secret. Use
   them to form a local `DATABASE_URL` with `sslmode=verify-full` and
   `sslrootcert`.
5. Run `python ../../database/migrate.py` from the repository root. This
   applies the same `database/migrations/001_initial_schema.sql` migration as
   the private stack.
6. Set the emitted input bucket, output bucket, and batch role ARN in the root
   `.env`; configure the existing Auth0 development tenant; then start the
   FastAPI and Next.js applications normally.

For local demo use, `tools/start-demo-api.ps1` retrieves the RDS-managed secret
at runtime, sets the required process-local database and HealthScribe variables,
checks the RDS connection, and starts FastAPI. It avoids storing the RDS
password in `.env`:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\start-demo-api.ps1
```

The AWS principal selected by `AWS_PROFILE` for the local FastAPI server must
also be allowed to start HealthScribe jobs, upload input audio, retrieve output,
and pass the batch role. Attach `healthscribe_caller_policy_arn` when it does
not already have equivalent permissions. An AWS IAM Identity Center permission
set may already grant these permissions; update that permission set rather than
attempting to attach a policy directly to an AWS-reserved SSO role.

The current onboarding endpoint persists Auth0-authenticated users,
organizations, memberships, practitioners, and an audit event in RDS. Auth0,
not RDS, handles sign-in and sign-out. Session/transcript artifact metadata is
not yet written into RDS by the application; today HealthScribe files are
uploaded to S3 and then also organized in local demo folders. That application
integration is the next step for account-scoped demo records.

## Teardown

RDS deletion protection is disabled in this demo root so the stack is actually
disposable. By default Terraform will refuse to delete non-empty artifact
buckets. Review their contents, then either empty them intentionally or run
destroy with `-var="force_destroy_artifact_buckets=true"` only for synthetic
demo objects.

By default RDS does not create a final snapshot. To retain one, apply with
`take_final_snapshot=true` and a unique `final_snapshot_identifier` before
destroying. Customer-managed KMS keys have AWS's seven-day minimum deletion
window, so the keys remain scheduled during that period.
