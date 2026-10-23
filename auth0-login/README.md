# Therapist Dashboard Auth0 ACUL login

This package builds the custom Auth0-hosted login screen for the combined
email/password `login` prompt. Auth0 remains responsible for credential
validation, password recovery, session creation, and token issuance.

The initial scope deliberately customizes only sign-in. The Create account link
uses the `signupLink` supplied by Auth0, so signup continues to use Auth0's
standard rendering until its onboarding design is approved.

## Local preview

```powershell
npm install
npm run dev
```

Open `http://localhost:3001`. Submission is disabled outside Auth0 because the
local preview has no Universal Login transaction context.

## Build

```powershell
npm run build
```

The deployable assets have stable names:

- `dist/assets/auth0-login.css`
- `dist/assets/auth0-login.js`

Host these assets on an HTTPS CDN with CORS enabled. Copy
`settings.example.json`, replace the asset origin, and configure the Auth0
combined login screen:

```powershell
auth0 ul customize --rendering-mode advanced --prompt login --screen login --file ./settings.json
```

ACUL currently requires an Auth0 Enterprise tenant and verified custom domain.
Use only a development tenant until the complete authentication flow has been
tested.

This first bundle targets Auth0's combined `login` screen. Configure the tenant
for the combined identifier-and-password prompt before activation. A tenant
using identifier-first login needs separate `login-id` and `login-password`
screens instead.

## Initial limitation

This minimal screen fails closed when Auth0 requests a CAPTCHA challenge. Do not
activate it on a tenant with bot-detection CAPTCHA enabled until the matching
Auth0 CAPTCHA provider component has been added and tested. Other screens such
as signup, MFA, and password reset retain standard Auth0 rendering.
