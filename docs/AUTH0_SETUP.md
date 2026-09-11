# Auth0 Development Setup

> Setup guide for the development tenant used by therapist onboarding. This is not authorization to process real clinical data. Complete the required contractual, legal, security, and privacy review before production use involving ePHI.

## 1. Create the development boundary

Create a dedicated Auth0 **development tenant**. Do not reuse it for staging or production, and do not create test users with real client or clinical data.

Create an Auth0 application of type **Regular Web Application** for the Next.js frontend.

## 2. Configure the application

For local development, set these values in the Auth0 Dashboard:

| Setting | Value |
| --- | --- |
| Allowed Callback URLs | `http://localhost:3000/auth/callback` |
| Allowed Logout URLs | `http://localhost:3000` |
| Allowed Web Origins | `http://localhost:3000` |

Enable a development database connection for email/password sign-up. Require email verification before treating an account as eligible for practice onboarding. Keep social sign-in and enterprise connections out of the first development flow unless they are intentionally being tested.

## 3. Configure the frontend locally

Copy `frontend/.env.example` to `frontend/.env.local`, then fill in the Auth0 application values:

```text
AUTH0_DOMAIN=<development-tenant-domain>
AUTH0_CLIENT_ID=<regular-web-application-client-id>
AUTH0_CLIENT_SECRET=<regular-web-application-client-secret>
AUTH0_SECRET=<random-64-character-hex-secret>
APP_BASE_URL=http://localhost:3000
```

`AUTH0_SECRET` encrypts the application session cookie; it is not the Auth0 client secret. Generate a new value for each environment. Never commit `.env.local` or paste secrets into issues, chat, or browser code.

## 4. Create the API audience

The web application login creates a browser session, but the FastAPI service
needs a separately scoped **access token** to verify requests. In Auth0,
create an API with these development values:

| Setting | Value |
| --- | --- |
| Name | `Therapist Dashboard API (development)` |
| Identifier | `https://api.therapist-dashboard.local` |
| Signing algorithm | `RS256` |

Add the exact Identifier to both the root `.env` used by FastAPI and
`frontend/.env.local` used by Next.js:

```text
AUTH0_AUDIENCE=https://api.therapist-dashboard.local
```

Restart both development servers after changing environment variables. The
audience is an identifier, not necessarily a public URL. Do not put clinical
roles, client access grants, session data, or other sensitive information into
Auth0 token claims; the application database remains the authorization source
of truth.

## 5. Test the therapist flow

1. Start the FastAPI server and the frontend development server.
2. Visit `http://localhost:3000/onboarding/therapist`.
3. Select **Create therapist account**.
4. Create and verify a development Auth0 account.
5. Return to the onboarding page and complete the practice details form.

Once the RDS migration has been applied and the FastAPI `DATABASE_URL` is
configured, submitting the form creates the practice organization, the
authenticated owner membership, a practitioner profile, and an audit event in
one database transaction. Until then, the form will correctly return a service
configuration error rather than storing any practice details locally.

## 6. Production decisions before enabling real accounts

- Obtain an appropriate Auth0 agreement/BAA and validate plan and deployment suitability before handling ePHI.
- Enable MFA for therapist and organization-administrator accounts; define step-up requirements for exports, access-management changes, and account recovery.
- Configure Auth0 Organizations only after deciding its operational ownership. Map its organization identifier to the application `organizations` record; do not make it the clinical authorization source of truth.
- Keep Auth0 metadata and tokens free of client, session, transcript, audio, diagnosis, consent-document, and clinical-access information.
- Implement RDS-backed user, organization, membership, practitioner, and audit records before granting any application clinical access.

## 7. Immediate infrastructure prerequisite

Provision the private RDS instance with Terraform, then run the initial
migration from an approved in-VPC migration environment. The RDS security group
intentionally has no public ingress, so a local laptop cannot connect directly.
See [the database migration guide](../database/README.md) for the runner and
[the storage architecture](storage-architecture/STORAGE_ARCHITECTURE.md) for
the boundary design.
