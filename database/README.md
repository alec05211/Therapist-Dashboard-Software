# Database migrations

`migrations/` contains ordered, immutable PostgreSQL migrations. `migrate.py`
applies each migration once and records its SHA-256 checksum in
`app.schema_migrations`.

## Deployment boundary

The checked-in `terraform/demo` stack currently provisions a **publicly
reachable, TLS-enforced RDS instance** restricted to `demo_allowed_cidr`. It is
for synthetic demonstration data only. Its Terraform does not currently
provision the Fargate migration runner or the private-network outputs used by
the historical instructions below.

Do not treat that demo topology as appropriate for identifiable clinical data.
For a real deployment, provision the private migration runner first and use it
to apply migrations from inside the database VPC. Until then, a direct
TLS-verified connection is the only available migration route for the demo
database; it must use the narrow operator CIDR and RDS-managed credentials.

## Apply migrations to the current synthetic demo

1. Configure and sign in to the restricted `terraform` AWS profile on the
   operator machine. Verify it with `aws sts get-caller-identity --profile terraform`.
2. Obtain the RDS-managed administrator secret and endpoint from the demo
   Terraform outputs. Build a TLS connection URL that uses `sslmode=verify-full`
   and the RDS CA bundle; do not place that URL or password in source control.
3. In that same short-lived shell, set `DATABASE_URL` and run
   `python database/migrate.py`. The migrator records the migration checksum in
   `app.schema_migrations`, so a successful rerun is a no-op.

## Future production database

The former private RDS and Fargate migration infrastructure has been retired.
Before the application handles identifiable clinical data, design and review a
new private production database boundary and an in-VPC migration path. Do not
reuse the public demo topology for that purpose.

## Local validation only

You may run `python database/migrate.py` against a local non-sensitive
PostgreSQL database or the synthetic demo database using the guarded process
above.
