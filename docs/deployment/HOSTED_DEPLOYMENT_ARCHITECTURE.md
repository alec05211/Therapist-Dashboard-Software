# Hosted deployment architecture

> A retained deployment direction for the Therapist Dashboard. This is a future implementation target, not a statement that the application is ready for real clinical use.

**Last updated:** 2026-10-05  
**Status:** Agreed direction — implement after the product-readiness gate below

## Decision summary

The first hosted environment should run the Next.js frontend and FastAPI backend on one small Amazon EC2 instance in `us-east-1`, with Caddy terminating HTTPS and routing requests. The application should use the existing RDS PostgreSQL database privately and access HealthScribe, S3, KMS, and Secrets Manager through an EC2 IAM instance role.

This is deliberately a compact staging and demonstration architecture for a solo developer and a small audience. It avoids splitting the application across several hosting vendors before the product workflows are stable, while preserving a direct path to larger AWS infrastructure later.

```text
Browser
   |
   | HTTPS
   v
Caddy on EC2
   +-- /* and Next.js routes --> Next.js production server :3000
   +-- /api/* and realtime traffic --> FastAPI :8000
                                           |
                                           +--> private RDS PostgreSQL
                                           +--> private S3 artifacts
                                           +--> HealthScribe
                                           +--> KMS and Secrets Manager
                                                through an EC2 IAM role
```

Caddy is not the frontend host. The Next.js process is the frontend host. Caddy is the public HTTPS and routing layer in front of both application processes.

## Initial infrastructure

- One EC2 `t4g.small` instance with 2 GB RAM, subject to a deployment-time compatibility check for ARM64 dependencies.
- Caddy listening on ports 80 and 443, automatically managing TLS certificates and routing one application domain.
- Next.js built in standalone production mode and run as a supervised service or container.
- FastAPI run as a separate supervised service or container.
- A private RDS PostgreSQL instance reachable only from the application security group.
- Private S3 buckets as the canonical location for recordings and provider artifacts.
- An EC2 IAM instance role with least-privilege application permissions; no long-lived AWS access key on the host.
- AWS Systems Manager Session Manager for administrative access instead of publicly exposing SSH.
- Route 53 or another DNS provider pointing the application domain at the server.
- Health checks, deployment logs, and application logs designed not to emit recordings, transcripts, clinical notes, tokens, or other sensitive content.

The recent working estimate for this compact environment is approximately **$36–38 per month before HealthScribe usage, domain registration, tax, and unusual traffic**. Recalculate prices before implementation.

For the synthetic demo phase, the hosted environment may use a temporary
DuckDNS subdomain instead of committing to the final product domain. The
hostname is an environment concern rather than a product or database identity;
replacing it later requires updating DNS, Caddy, Auth0 URLs, and deployment
configuration, but does not require replacing RDS or changing browser API
paths. Do not carry the shared free-domain dependency into real clinical use.

The synthetic demo infrastructure has two Terraform lifecycle boundaries:

- `terraform/demo` owns the persistent demo VPC, public mock-data-only RDS,
  encrypted artifact buckets, KMS keys, and the security-group identity trusted
  by RDS;
- `terraform/demo-app` owns the replaceable EC2 host, Elastic IP, public web
  security group, Caddy bootstrap, instance profile, and application IAM role.

Destroying `terraform/demo-app` must not destroy or recreate the data stack.
The later real-data environment remains a separate private deployment rather
than an in-place conversion of the public synthetic database.

## Development workflow before and after hosting

Hosting should not replace the local development loop.

### Local loop

Use local Next.js hot reload and the local FastAPI reload server for rapid UI and workflow development. This remains the default loop for layout work, interaction design, and most implementation changes.

### Hosted checkpoint loop

Use the EC2 environment to verify behavior that is difficult to establish locally:

- production builds and process startup;
- HTTPS, Auth0 callbacks, cookies, and same-origin routing;
- private RDS connectivity and migrations;
- IAM-role access to S3, KMS, Secrets Manager, and HealthScribe;
- durable processing across browser navigation and application restarts;
- uploads, playback, and realistic network behavior;
- environment-specific security and logging behavior.

GitHub Actions does not need to be the first deployment mechanism. The first hosted iteration may use a documented manual deployment script or a manually triggered workflow. Automatic deployment from the main branch should be added only after the production build and restart procedure are repeatable. Even after automation exists, developers should evaluate most changes locally and deploy coherent checkpoints rather than using the live environment as the primary CSS or interaction-design loop.

## Product-readiness gate before the first hosted pivot

The application does not need to be feature-complete. It should have one stable, valuable, synthetic-data vertical slice and clear boundaries around unfinished work.

### 1. Settle the Insights workspace information architecture

This is the highest-priority product decision before hosting. The current implementation already exposes both the generated Insights workspace and the client journey material in the same Insights route. Before the hosted pivot, establish:

- the top-to-bottom hierarchy of the page;
- the distinction between the concise generated overview and the evidence-rich clinical journey;
- the treatment of one-session observations versus multi-session trajectories and recurring themes;
- how accepted, draft, hidden, stale, and disputed material appears;
- how a therapist opens the exact session, transcript segment, and synchronized audio evidence;
- how correction, acceptance, hiding, pinning, and staleness controls fit without making the page feel like an indiscriminate client dossier;
- useful empty, loading, error, single-session, multi-session, and partially reviewed states.

The layout does not need final visual polish, but its conceptual hierarchy and main review interactions should be stable enough that hosting will produce meaningful product feedback rather than feedback about an obviously transitional structure.

### 2. Stabilize the core therapist session loop

Demonstrate the following end to end with synthetic data:

1. Select or schedule a session.
2. Record or upload audio.
3. Complete the durable upload handoff.
4. Resume and display HealthScribe processing state after navigation or restart.
5. Review synchronized transcript and audio.
6. Correct speaker identities.
7. Review and finalize the draft clinical note.
8. Surface source-linked longitudinal material for therapist review.
9. Carry accepted material into the bounded pre-session brief.

### 3. Remove host-local clinical data as a required source of truth

The hosted application must not depend on one EC2 filesystem for durable recordings, transcripts, or generated artifacts. S3 and PostgreSQL should remain canonical. Any temporary local file must have a deliberate lifecycle, restrictive permissions, and cleanup behavior.

### 4. Validate authorization and isolation

- Auth0 production callbacks and logout URLs are defined.
- Every clinical API verifies organization, therapist-client relationship, and permission boundaries on the server.
- Client sharing exposes only therapist-approved material.
- Synthetic test cases cover cross-client and cross-organization denial paths.

### 5. Make startup and schema changes reproducible

- Required environment variables are documented and validated at startup.
- Database migrations run through a reviewed, repeatable command rather than ad hoc SQL.
- Production builds, process startup, health checks, and rollback steps are documented.
- Secrets are supplied through the approved AWS boundary and are not committed or copied into images.

### 6. Add a small hosted smoke-test suite

The initial gate is not comprehensive automated testing. It is a dependable check that login, client selection, session review, Insights evidence navigation, recording playback, and one synthetic upload-processing path still work after a deployment.

## Work that can remain unfinished at the first hosted pivot

- Final pixel polish throughout every secondary screen.
- Complete practice billing and insurance workflows.
- The full client mobile experience.
- Multi-instance scaling and autoscaling.
- A custom transcription or longitudinal model.
- Fully automatic continuous deployment.
- Production approval for real therapy data.

The first hosted environment should use synthetic demonstration data unless and until the privacy, consent, security, legal, retention, contractual, and clinical-policy gates for real therapy information have been explicitly established.

## Scaling path

1. Vertically resize the EC2 instance if CPU or memory becomes constrained.
2. Separate the Next.js and FastAPI processes into independently deployable containers or instances.
3. Place an Application Load Balancer in front of an Auto Scaling Group or move the services to ECS when horizontal scaling is justified.
4. Move HealthScribe orchestration and other durable background work into dedicated workers so web instances can be replaced or multiplied safely.
5. Resize RDS independently and add appropriate availability, backup, monitoring, and connection-management controls.

Before running more than one backend instance, verify that job ownership, locks, processing recovery, and all canonical artifacts are distributed through PostgreSQL, S3, or an appropriate queue rather than process memory or a node-local filesystem.

## Related documents

- [Project vision](../product/PROJECT_VISION.md)
- [AI / ML vision](../ai/AI_ML_VISION.md)
- [Current HealthScribe implementation](../ai/HEALTHSCRIBE.md)
- [Clinical AI orchestration and evidence harness](../ai/harness/ARCHITECTURE.md)
- [Longitudinal record lifecycle](../ai/harness/LONGITUDINAL_RECORD_LIFECYCLE.md)
- [Storage architecture](../data/storage-architecture/STORAGE_ARCHITECTURE.md)
- [Local startup guide](startup.md)
