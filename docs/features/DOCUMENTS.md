# Relationship documents

The Documents tab is shared by one client and one therapist within an organization.
An active therapist with write access can upload a PDF and optionally request the
client's signature. The linked client can read and sign it with a typed name and
explicit consent. Both people can review/download the original and signed copy.

Uploads are limited to 20 MiB and 100 pages. Encrypted PDFs, embedded attachments,
and detected active content are rejected. Pages are rendered as images for the
in-app viewer; a thumbnail is stored with each new upload. The UI retains the
existing grid/list views without adding sorting or folder management.

## Storage and access

- Migration `016_relationship_documents.sql` adds the practitioner scope and
  signature fields. Legacy documents are assigned to their uploader's practitioner
  membership; unresolved rows remain inaccessible until explicitly assigned.
- Every list, original, thumbnail, page, signed-copy, upload, and signature request
  resolves the authenticated identity against the active relationship. Client
  identities cannot upload; therapist identities cannot sign for a client.
- Files use the organization's private KMS-encrypted S3 storage. Random keys and
  stored object versions preserve the original. Storage locations are never sent
  to the browser; authenticated API handlers proxy the content with `no-store`.
- A signature appends a signature page to a separate PDF. The database stores the
  verified client portal account, typed name, exact consent, server UTC timestamp,
  and original SHA-256. A row lock prevents concurrent/repeated signatures.
- This is a typed electronic-signature workflow, not a certificate-backed digital
  signature service. Signature placement, countersigning, stronger identity
  verification, and jurisdiction-specific legal requirements are separate work.

## Setup and verification

Install the updated `requirements.txt`, then apply migrations through
`python -m tools.apply_session_review_migration` with the configured development
AWS profile and database credentials. Restart the API after installation.

Run `python -m unittest discover -s tests -p 'test_*.py'`, frontend TypeScript, and
ESLint checks. Test with synthetic files in both roles: upload, read, sign, reopen,
and download both versions; verify another therapist/client cannot access any
asset URL. The client Documents tab does not depend on session-sharing toggles.

Database transactions prevent partial catalog/signature updates. S3 and PostgreSQL
do not share a transaction: a storage write followed by a database failure can
leave an unreferenced private object. Such objects need retention/reconciliation
before production rollout; retries never overwrite an existing document object.
