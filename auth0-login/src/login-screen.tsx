import { useMemo, useState, type FormEvent } from "react";

import Login from "@auth0/auth0-acul-js/login";
import type { Error as Auth0Error } from "@auth0/auth0-acul-js/types";

function BrandMark() {
  return (
    <svg aria-hidden="true" className="brand-mark" fill="none" viewBox="0 0 32 32">
      <path d="M7.5 18.25c0-6.25 3.35-10.5 8.5-10.5s8.5 4.25 8.5 10.5" stroke="currentColor" strokeLinecap="round" strokeWidth="2.25" />
      <path d="M11 19.25c0-4.25 1.85-7 5-7s5 2.75 5 7" stroke="currentColor" strokeLinecap="round" strokeWidth="2.25" />
      <path d="M16 16.75v8" stroke="currentColor" strokeLinecap="round" strokeWidth="2.25" />
    </svg>
  );
}
function EyeIcon({ hidden }: { hidden: boolean }) {
  return (
    <svg aria-hidden="true" fill="none" viewBox="0 0 24 24">
      <path d="M2.75 12s3.25-6 9.25-6 9.25 6 9.25 6-3.25 6-9.25 6S2.75 12 2.75 12Z" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8" />
      <circle cx="12" cy="12" r="2.5" stroke="currentColor" strokeWidth="1.8" />
      {hidden ? <path d="m4 4 16 16" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" /> : null}
    </svg>
  );
}
export function LoginScreen({ preview = false }: { preview?: boolean }) {
  const login = useMemo(() => (preview ? null : new Login()), [preview]);
  const screen = login?.screen;
  const transaction = login?.transaction;
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const errors = (login?.getErrors() ?? []) as Auth0Error[];
  const hasCaptcha = Boolean(screen?.isCaptchaAvailable);
  const signupLink = screen?.signupLink;
  const resetPasswordLink = screen?.resetPasswordLink;
  const signupEnabled = transaction?.isSignupEnabled ?? true;
  const forgotPasswordEnabled = transaction?.isForgotPasswordEnabled ?? true;

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!login || hasCaptcha) return;
    setSubmitting(true);
    try {
      await login.login({ username: username.trim(), password });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="sign-in-title">
        <aside className="brand-panel">
          <div>
            <div className="brand-lockup">
              <span className="brand-icon"><BrandMark /></span>
              <span>Therapist Dashboard</span>
            </div>
            <h2>Return to the full story of care.</h2>
            <p>One secure account opens the workspace appropriate to you.</p>
          </div>
          <p className="privacy-note">Authentication and account recovery are securely handled by Auth0.</p>
        </aside>

        <div className="form-panel">
          <h1 id="sign-in-title">Sign in securely</h1>
          <p className="form-intro">Use the same sign-in whether you are a therapist, client, or practice administrator.</p>

          {errors.length ? (
            <div className="error-message" role="alert">
              {errors.map((error, index) => <p key={`${error.message}-${index}`}>{error.message}</p>)}
            </div>
          ) : null}

          {hasCaptcha ? (
            <div className="error-message" role="alert">
              Additional verification is required. This initial custom login does not yet render Auth0 CAPTCHA challenges, so standard rendering must remain enabled when bot detection is active.
            </div>
          ) : null}

          <form onSubmit={submit}>
            <label htmlFor="username">Email address</label>
            <input
              id="username"
              name="username"
              type="email"
              autoComplete="username"
              inputMode="email"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              autoFocus
            />

            <div className="password-heading">
              <label htmlFor="password">Password</label>
              {forgotPasswordEnabled && resetPasswordLink ? <a href={resetPasswordLink}>Forgot password?</a> : null}
            </div>
            <div className="password-field">
              <input
                id="password"
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
              <button type="button" className="password-toggle" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Hide password" : "Show password"}>
                <EyeIcon hidden={showPassword} />
              </button>
            </div>

            <button className="primary-action" type="submit" disabled={submitting || hasCaptcha || preview}>
              {submitting ? "Signing in..." : "Sign in"}
            </button>
          </form>

          {preview ? <p className="preview-note">Local preview. Auth0 enables submission when this bundle runs inside Universal Login.</p> : null}

          {signupEnabled ? (
            <div className="signup-row">
              <span>New to Therapist Dashboard?</span>
              {signupLink ? <a href={signupLink}>Create an account</a> : <span className="signup-placeholder">Create an account</span>}
            </div>
          ) : null}
        </div>
      </section>
    </main>
  );
}

