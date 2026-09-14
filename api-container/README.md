# Private API service

This container runs the FastAPI application as a private AWS Fargate service.
It is the production path for database-backed application operations, including
therapist onboarding. The browser never receives RDS credentials and RDS is
never made public.

## What Terraform creates when enabled

- An immutable ECR repository and an ECS task definition for the API.
- A separate API task role and execution role. The task receives only the
  RDS username and password fields from the RDS-managed Secrets Manager secret.
- A private API task security group with only DNS, HTTPS, S3, and PostgreSQL
  paths needed by the application.
- Two NAT gateways and private-subnet routes for outbound HTTPS. This is needed
  to validate Auth0 access tokens against Auth0's public signing-key endpoint;
  it does not create inbound internet access to the API or database.

The Terraform defaults create none of the service or NAT resources. The API
service is intentionally private until a product domain exists and a later
HTTPS load-balancer deployment is configured.

## Build and publish the API image

First create the repository and supporting roles without starting the service.
If you are retaining the currently available migration path, keep its network
flag enabled as shown:

```powershell
terraform apply -var="enable_migration_task_network=true"
```

```powershell
$env:AWS_PROFILE = "terraform"
$env:AWS_REGION = "us-east-1"
$repository = terraform output -raw api_repository_url

aws ecr get-login-password | docker login --username AWS --password-stdin $repository.Split('/')[0]
docker build -f api-container/Dockerfile -t therapist-dashboard-api:initial .
docker tag therapist-dashboard-api:initial "${repository}:initial"
docker push "${repository}:initial"
```

Use a new immutable tag for every subsequent image release and pass it as
`-var="api_image_tag=<tag>"` to Terraform.

## Enable the private service

The Auth0 domain and API audience are configuration values, not secrets. Do
not put the Auth0 client secret or the browser-session secret in Terraform.

```powershell
terraform apply `
  -var="enable_api_service=true" `
  -var="enable_api_internet_egress=true" `
  -var="auth0_domain=<your-auth0-tenant-domain>" `
  -var="auth0_audience=<your-auth0-api-identifier>"
```

Wait for the ECS service to show a running task, then inspect its operational
logs:

```powershell
aws logs tail "/therapist-dashboard/api" --follow
```

## Deliberately deferred

The service has no public listener yet. Before a browser can call it, add the
domain-dependent edge layer: ACM certificate, HTTPS-only Application Load
Balancer, API DNS record, CORS allowlist, rate limiting/WAF decision, and
production Auth0 callback/logout URLs.
