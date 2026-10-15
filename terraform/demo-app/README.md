# Replaceable EC2 hosted-demo stack

This Terraform root creates the replaceable compute layer for the synthetic
demo. It does not own RDS, S3, KMS, or their VPC. Destroying this root removes
EC2, its Elastic IP, web security group, instance profile, and application IAM
role while retaining the data stack in `terraform/demo`.

The first implementation phase provisions:

- one ARM64 Amazon Linux 2023 `t4g.small` instance;
- an encrypted gp3 root volume;
- IMDSv2 with a container-compatible hop limit;
- no inbound SSH, with Session Manager for administration;
- ports 80 and 443 for Caddy;
- the persistent database-client security group from `terraform/demo`;
- a scoped EC2 instance role for the RDS-managed secret and existing
  HealthScribe caller policy;
- organization-scoped S3/KMS policies exported by the persistent organization
  storage stack, so completed session artifacts remain readable after compute
  teardown and recreation;
- a Caddy container with automatic HTTPS and an infrastructure health route.

The application processes are deliberately a separate deployment step. The
host will return a proxy error for application routes until Next.js and FastAPI
have been installed. This prevents Auth0 or other runtime secrets from entering
Terraform state, EC2 user data, or an image. The repository includes repeatable
ARM64 container builds and `deploy/hosted-demo/deploy.sh` for that step. The
script resolves Secrets Manager dynamic references only inside the migration
and container-launch processes; plaintext runtime `.env` files are not used.

## Prerequisites

1. Apply `terraform/demo` so its new database-client security group exists.
2. Register a free DuckDNS subdomain and keep its token outside this repository.
3. Export the data-stack identifiers:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\export-demo-app-tfvars.ps1 `
  -DomainName therapist-dashboard-demo.duckdns.org
```

The generated `terraform.auto.tfvars.json` is ignored by Git. It contains
resource identifiers, organization storage policy ARNs, and the managed-secret
ARN, never the secret value. Apply `terraform/organizations` before exporting
when organization-backed session storage is enabled.

## Plan and apply

```powershell
$env:AWS_PROFILE = "terraform"
terraform -chdir=terraform/demo-app init
terraform -chdir=terraform/demo-app plan -out=demo-app.tfplan
terraform -chdir=terraform/demo-app apply demo-app.tfplan
```

Update DuckDNS with the emitted Elastic IP without printing the token:

```powershell
$env:DUCKDNS_TOKEN = "set-this-only-in-the-current-shell"
powershell -ExecutionPolicy Bypass -File .\tools\update-duckdns.ps1 `
  -Subdomain therapist-dashboard-demo `
  -IpAddress (terraform -chdir=terraform/demo-app output -raw public_ip)
```

Once DNS resolves, Caddy obtains the public certificate automatically. Check:

```powershell
terraform -chdir=terraform/demo-app output -raw caddy_health_url
```

## GitHub Actions prerequisites

The repository exposes two manual infrastructure workflows, `Terraform - Demo
Data` and `Terraform - Demo Hosted App`, plus the `Deploy - Hosted Demo`
application workflow. Before using them, configure:

- repository variable `AWS_TERRAFORM_APP_ROLE_ARN` with the application OIDC
  role output by `terraform/bootstrap`;
- repository variable `AWS_TERRAFORM_DATA_ROLE_ARN` with the persistent-data
  OIDC role output by `terraform/bootstrap`;
- repository variable `AWS_REGION` (normally `us-east-1`);
- repository variable `TF_STATE_BUCKET` naming a pre-created encrypted,
  versioned S3 state bucket;
- repository variable `DEMO_ALLOWED_CIDR` with the current operator `/32`;
- repository variable `DUCKDNS_SUBDOMAIN` containing only the label;
- `DUCKDNS_TOKEN` as a secret in the protected `demo-app` environment;
- required reviewers on the `demo-data-destroy` environment.

After authenticating the GitHub CLI, the repository environments, non-secret
variables, and DuckDNS environment secret can be configured without exposing
the token in a command line or file:

```powershell
gh auth login
.\tools\configure-github-demo-deployment.ps1 -DemoAllowedCidr "YOUR.PUBLIC.IP/32"
```

The script prompts for the DuckDNS token with hidden input. Add the required
reviewer for `demo-data-destroy` in the GitHub web settings afterward.

The existing bootstrap, data, and hosted-app states must be migrated once
before a workflow is used. Their committed backend blocks are partial; supply
the same bucket and Region plus keys `therapist-dashboard/bootstrap.tfstate`,
`therapist-dashboard/demo-data.tfstate`, and
`therapist-dashboard/demo-app.tfstate`. Enable encryption and native S3
lockfiles. Review `terraform state list` after migration. Never start a
workflow against an empty remote state while the resources already exist.

## Runtime secrets and application deployment

Do not put the DuckDNS token, Auth0 client secret, Auth0 session secret, database
password, or other credentials in Terraform variables. The host contains only
non-secret runtime identifiers at
`/etc/therapist-dashboard/runtime-identifiers.env`. Auth0 settings are stored
as one JSON secret in the persistent data stack and resolved at process launch
through `deploy/hosted-demo/asm-exec`. The EC2 role can read only that exact
secret and the existing RDS-managed credential secret.

Clone a reviewed revision and deploy it:

```bash
sudo git clone https://github.com/alec05211/Therapist-Dashboard-Software.git /opt/therapist-dashboard/source
cd /opt/therapist-dashboard/source
sudo bash deploy/hosted-demo/deploy.sh
```

After the GitHub application role includes the SSM deployment permissions from
`terraform/bootstrap`, every push to `main` automatically runs `Deploy - Hosted
Demo` for the pushed commit. The workflow can also be started manually from the
`main` branch with a branch, tag, or commit for an explicit redeploy or rollback.
It first lints, type-checks, and builds the frontend and runs the Python test
suite. Only a validated revision proceeds to deployment. The workflow resolves
that revision to an immutable commit SHA, reads the current instance ID from
remote Terraform state, and invokes the same deployment script through Systems
Manager Run Command. It waits for container health checks and then verifies the
public infrastructure and login endpoints. The protected `demo-app` environment
can require a reviewer before AWS credentials are issued.

The workflow does not place application secrets in GitHub. The EC2 instance
continues to resolve its narrowly scoped Secrets Manager values at process
launch through its instance role. GitHub receives only the SSM command output;
the deployment script and application logs must therefore continue to avoid
printing tokens, transcripts, recordings, clinical notes, or other sensitive
content.

The script builds the migration, API, and frontend images before replacing
either running container. It applies ordered database migrations, checks the
private API and frontend ports, and preserves the synthetic recordings volume
across container restarts. RDS credentials are resolved only for the migration
and API processes through the EC2 instance role.

## Destroy only compute

```powershell
terraform -chdir=terraform/demo-app plan -destroy -out=demo-app-destroy.tfplan
terraform -chdir=terraform/demo-app apply demo-app-destroy.tfplan
```

This releases the Elastic IP and removes the EC2 layer. The DuckDNS record will
still contain the old address until the next apply/update, but RDS and synthetic
artifacts remain intact.
