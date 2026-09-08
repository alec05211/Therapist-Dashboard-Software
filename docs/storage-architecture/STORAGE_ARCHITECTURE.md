# Storage Architecture

> The source of truth for how the product stores, relates, protects, and audits operational and clinical data. This is an approved architecture direction, not a claim of HIPAA compliance or legal advice.

**Last updated:** 2026-09-08  
**Status:** Approved direction — implementation in backlog  
**Related:** [Project vision](../PROJECT_VISION.md), [AI / ML vision](../AI_ML_VISION.md), [current HealthScribe implementation](../HEALTHSCRIBE.md)

**Schema diagram:** [PNG](schema-diagram.png) · [Mermaid source](schema-diagram.mmd)

## 1. Purpose

The product needs one coherent therapist-client record while safely handling two very different kinds of data:

- **Relational product data:** accounts, organization membership, preferences, scheduling, consent, therapist-client relationships, billing references, and artifact metadata.
- **Large clinical artifacts:** recordings, raw transcription provider results, transcript exports, generated documents, and future permitted attachments.

The architecture must support a solo practitioner and a large organization without a later tenant-data migration. It must also preserve therapist control, source provenance, consent, least-privilege access, and auditability for sensitive therapy information.

## 2. Decisions

1. **AWS is the initial storage platform.** Amazon RDS for PostgreSQL is the relational system of record, and private Amazon S3 is the clinical artifact vault.
2. **Every practice is an organization.** A solo practice is an organization with one therapist member; there is no separate single-practice data model.
3. **Auth0 is the initial identity platform.** It authenticates people and provides organization-context information. It is not the source of truth for clinical permissions or clinical data.
4. **PostgreSQL does not store recording bytes or document files.** It stores the metadata, authorization context, lifecycle state, and opaque reference to the S3 object.
5. **Organization membership is not clinical access.** Being in the same practice never by itself grants access to a client's clinical record.
6. **Clinical access is relationship-based, explicit, time-bounded where appropriate, and auditable.** A client may have multiple approved therapists with different capabilities.
7. **AI outputs are versioned drafts with provenance.** They never replace therapist judgment and must remain traceable to source material where appropriate.

## 3. System boundary

```text
Person
  -> Auth0: identity, authentication, MFA, selected organization context
  -> Application API: policy enforcement and audit creation
  -> RDS PostgreSQL: relational records, permissions, metadata, versions, audit events
  -> S3: encrypted audio and document objects

HealthScribe / future processor
  -> restricted processing identity
  -> private processing input/output objects
  -> raw provider artifact + normalized, versioned application record
```

The API is the only normal route to protected data. It checks identity, selected organization, organization membership, client relationship, consent, and requested operation before reading PostgreSQL data or issuing narrowly scoped, short-lived artifact access.

## 4. Logical tenancy and relationships

Each row containing protected product or clinical information belongs to exactly one `organization`. User identity is global; people may have memberships in one or more organizations.

```text
application_user (Auth0 subject is an external reference)
  -> organization_membership
       -> organization
       -> practitioner profile / operational role

organization
  -> client
       -> client_therapist_access[]
       -> appointment[]
       -> session[]
            -> clinical_artifact[]
            -> transcript_version[]
            -> synthesis_version[]
            -> audit_event[]
```

`organizations.id`, `clients.id`, `sessions.id`, and artifact identifiers are application-generated immutable UUIDs. Auth0 organization and user IDs are external references, not primary keys for business data.

### Core records

| Record | Responsibility |
| --- | --- |
| `organization` | Practice boundary, settings, approved retention policy, and billing configuration. |
| `application_user` | Product profile linked to an Auth0 `sub`; contains no clinical content. |
| `organization_membership` | A person's role in an organization, start/end dates, and status. |
| `client` | Client identity and administrative profile within one organization. |
| `client_therapist_access` | A specific therapist's approved relationship and capabilities for one client. |
| `appointment` | Scheduling record. |
| `session` | Clinical-session container, including consent and lifecycle state. |
| `clinical_artifact` | Metadata and storage reference for an audio or document object. |
| `transcript_version` / `synthesis_version` | Reviewable, immutable-version content and provenance. |
| `audit_event` | Append-only account of sensitive actions and decisions. |

## 5. Multi-therapist client access

A `client_therapist_access` record, rather than a single `client.therapist_id`, governs which therapist may work with a client. It includes:

- organization, client, and therapist identifiers;
- relationship type: `primary`, `collaborating`, `supervising`, or `temporary_coverage`;
- effective start and optional end time;
- explicit capabilities: `read_clinical`, `write_clinical`, `manage_client_access`, `view_artifacts`, `export`, and `manage_session`;
- grant source, granting actor, rationale where policy requires it, and revocation information.

The **primary therapist** normally receives read/write clinical access and manages the approved therapist list. Supervisors, collaborators, and temporary cover therapists receive only the capabilities deliberately granted for their role. For example, a supervisor may be granted review access and the ability to add supervisory input; a covering therapist can be granted temporary read/write session access with an expiry date. The application must not infer those rights solely from title or organization membership.

Every authorization decision must be evaluated at request time. A revoked or expired relationship immediately prevents new access, including artifact-link generation. Existing downloaded copies and mandatory records remain subject to approved policy and cannot be erased by access revocation alone.

## 6. Authentication and authorization boundary

Auth0 is responsible for authentication, MFA, session security, and organization login context. The application is responsible for clinical authorization.

- Use Auth0 Organizations to represent practice membership where the selected plan supports it.
- Maintain separate Auth0 tenants/configuration for development, staging, and production.
- Store only minimum identity attributes in Auth0; do not place clinical text, clinical consent documents, diagnoses, session metadata, or audio references in Auth0 profiles, tokens, Actions, or logs.
- Require MFA for therapists and organization administrators. Require step-up authentication for high-risk actions such as export, access-management change, and account recovery.
- Validate issuer, audience, signature, expiry, subject, and organization context for every API token.
- Treat Auth0 role claims as an input to application policy, not final permission to a particular client or session.

Before real ePHI is handled, obtain the required agreements (including a BAA where applicable), confirm the plan and deployment are suitable, and complete legal/security review.

## 7. Data placement

### RDS PostgreSQL

RDS PostgreSQL holds transactional, relational, and queryable data:

- accounts and application profiles;
- organizations, memberships, roles, therapist-client access grants;
- client administrative data, appointments, and session metadata;
- consent state, retention state, legal hold state, and deletion requests;
- transcript segments and generated-output text when needed for application review/search;
- artifact metadata: opaque object key, object version, checksum, media type, size, encryption-key reference, and lifecycle state;
- model/provider version, source version, reviewer, acceptance/rejection state, and source links;
- append-only application audit events.

Sensitive rows include `organization_id`; application queries must scope it explicitly. PostgreSQL row-level security may provide defense in depth, but it never replaces API authorization tests.

### Amazon S3

S3 holds large immutable or versioned artifacts:

- recording audio;
- raw HealthScribe input/output and equivalent future-provider output;
- normalized transcript or clinical-document files when stored as files;
- approved exports and permitted attachments;
- separate protected infrastructure audit-log objects.

Object keys must be opaque and non-identifying. Do not include names, emails, therapist names, diagnoses, or session narrative in keys, tags, URLs, filenames, or ordinary logs. The database maps an artifact identifier to its S3 object.

Use separate private locations for clinical artifacts, processor input/output, exports, and immutable audit logs. Public access is blocked. Objects are encrypted with approved customer-managed KMS keys and are accessible only through least-privilege service identities.

## 8. Session-artifact lifecycle

1. An authorized therapist creates a session in PostgreSQL.
2. The API authorizes a narrowly scoped, short-lived upload to the processing or clinical-artifact location.
3. The application records artifact metadata, checksum, ownership, consent state, and lifecycle state.
4. A processor such as HealthScribe reads only the input it needs and writes raw output to its restricted location.
5. The application creates normalized transcript and synthesis versions without overwriting raw or reviewed versions.
6. An authorized user requests playback/download. The API re-evaluates access and creates a short-lived, object-specific retrieval route or signed URL.
7. The application logs the action. Retention, legal-hold, and deletion workflows govern later lifecycle changes.

The local `recordings/` directory is development-only and must not be treated as a secure production store.

## 9. AI, transcript, and source provenance

The system retains distinct layers:

1. raw provider output;
2. normalized application transcript;
3. therapist corrections/finalized transcript version;
4. generated synthesis/draft note version;
5. therapist review, edit, acceptance, or rejection.

Every generated output records its input transcript version, source artifact references, generator/provider and version, creation time, review state, and authoring identity. Reprocessing creates a new version; it does not overwrite a reviewed clinical record.

Production clinical data is not a training or evaluation dataset by default. Any future model-evaluation/training corpus requires separate explicit consent, governance, access controls, purpose limitation, lineage, retention, and audit evidence.

## 10. Audit, consent, retention, and deletion

### Application audit

The application creates append-only audit events for protected actions, including access, playback, download, edit, export, share, consent change, relationship-grant change, deletion request, legal hold, and privileged or break-glass access. Each event records actor, organization, target, action, time, request context, outcome, and applicable version identifiers.

### Infrastructure audit

AWS-level logging records S3, KMS, IAM, and configuration activity in a separate protected log archive. These logs complement application events; they do not replace them.

### Consent and lifecycle controls

Consent is an explicit versioned record, not a checkbox lost in a UI. It records scope, policy/text version, actor, time, withdrawal state, and the affected processing/storage use.

Retention and deletion are policy-driven and must be approved through legal, clinical, and security review before production use. A deletion workflow must account for PostgreSQL records, S3 objects and versions, generated derivatives, search indexes, and backups according to the approved policy. Legal holds suspend applicable destruction and are themselves auditable.

## 11. Security and operations baseline

- Encrypt data in transit and at rest; use customer-managed KMS keys for sensitive S3 data and approved RDS encryption.
- Use least-privilege, separately identifiable service roles for the API, processors, deployment, and audit access.
- Keep production, staging, and development separate; never copy production clinical data into non-production without an approved governed process.
- Store secrets in a secrets manager, never in source control, application logs, or client bundles.
- Use encrypted backups, defined recovery objectives, and documented restore drills for RDS and artifacts.
- Monitor and alert on sensitive configuration changes, failed/abnormal access patterns, backup failures, and key/authorization failures.
- Maintain incident response, access review, and emergency-access procedures before live clinical use.

## 12. Explicit non-goals

- A single database containing binary audio or document files.
- Public S3 objects, permanent artifact URLs, or browser-held AWS credentials.
- Broad organization-wide access to all client clinical records.
- Storing card numbers or CVVs; a PCI-compliant payment provider handles card data and the product retains only required references.
- Treating generated summaries or model-derived insights as authoritative clinical conclusions.
- Using production session data to train or evaluate models without separate approval and governance.

## 13. Implementation sequence

1. Implement the core PostgreSQL data model and migrations.
2. Provision the private S3 artifact vault and database-to-object metadata contract.
3. Integrate Auth0 authentication and organization context.
4. Implement therapist-client authorization and time-bounded access grants.
5. Add artifact upload/retrieval through API authorization.
6. Add application audit events and protected AWS audit logging.
7. Add transcript/synthesis versioning and provenance.
8. Implement consent, retention, legal-hold, deletion, recovery, and production-readiness controls.

The initial adaptable relational schema is maintained in [database/schema.sql](../../database/schema.sql). It establishes the core tenant, client, therapist-access, session, artifact, transcript, synthesis, consent, and audit records without committing to a final practice workflow or demographic-data model.

## 14. Open decisions

- Exact data-retention schedules and deletion obligations, pending legal and clinical-policy review.
- Client-facing access policy for recordings, transcripts, summaries, and exports.
- The exact default capability sets for supervisor, collaborator, and temporary-coverage relationships.
- Which actions require step-up authentication and whether break-glass access will be available in the first production release.
- Auth0 plan, BAA, production deployment, and organization-feature configuration.

Update this document whenever those decisions become explicit or the storage boundary changes.
