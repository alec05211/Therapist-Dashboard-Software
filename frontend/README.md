# Therapist Sidekick frontend

The therapist web portal is a [Next.js](https://nextjs.org) application built with React, TypeScript, and Tailwind CSS. The existing FastAPI service remains responsible for HealthScribe and transcript APIs.

## Local development

Start the FastAPI service in one terminal from the repository root. Using the
virtual environment's Python directly avoids needing to activate it first:

```powershell
.\.venv\Scripts\python.exe -m uvicorn server:app --reload --port 8000
```

If the `.venv` folder does not exist yet, create it and install the backend
dependencies first:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then start Next.js in a second terminal:

```powershell
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Requests sent to `/api/*` are proxied to `http://127.0.0.1:8000/*` during local development, so browser code should use `/api/transcripts`, `/api/transcribe`, and related API paths rather than hard-coding a backend host.

To point the frontend at a different API host, create `frontend/.env.local`:

```text
API_ORIGIN=https://your-api.example.com
```

Never place sensitive credentials or HealthScribe configuration in a `NEXT_PUBLIC_*` variable: those values are exposed to the browser.

## Validation

```powershell
npm run lint
npm run build
```
# Frontend

## Auth0 development setup

The therapist onboarding flow uses the official Auth0 Next.js SDK. Before testing
sign-up locally, create a **Regular Web Application** in an Auth0 development
tenant and copy `frontend/.env.example` to `frontend/.env.local`.

Set the Auth0 application URLs to:

- Allowed Callback URLs: `http://localhost:3000/auth/callback`
- Allowed Logout URLs: `http://localhost:3000`

Do not place clinical, client, or practice data in Auth0 metadata or tokens.
Auth0 creates the account identity; the RDS-backed onboarding endpoint will
create the organization, membership, and practitioner profile.
