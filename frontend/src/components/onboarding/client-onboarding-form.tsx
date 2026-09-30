"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

export function ClientOnboardingForm({ firstName = "", lastName = "", email }: { firstName?: string; lastName?: string; email?: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ name: string; connected: boolean } | null>(null);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy(true); setError(null);
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/onboarding/client", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({
        first_name: form.get("firstName"), last_name: form.get("lastName"), discoverable: form.get("discoverable") === "on",
      }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Your client account could not be created.");
      setResult({ name: body.name, connected: Boolean(body.connected) });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Your client account could not be created."); }
    finally { setBusy(false); }
  };

  if (result) return <section className="rounded-2xl border border-stone-300 bg-white p-6 shadow-sm">
    <h1 className="text-2xl font-semibold text-stone-900">Your client account is ready</h1>
    <p className="mt-3 text-sm leading-6 text-stone-600">{result.connected ? `${result.name} is connected to your care workspace.` : `A therapist can now find ${result.name} by first name, last name, or sign-in email and send a care connection.`}</p>
    {result.connected ? <Link href="/" className="mt-5 inline-flex cursor-grab rounded-xl bg-emerald-800 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-900 active:cursor-grabbing">Open your portal</Link> : null}
  </section>;

  return <form onSubmit={submit} className="space-y-6 rounded-2xl border border-stone-300 bg-white p-6 shadow-sm sm:p-8">
    <div className="grid gap-5 sm:grid-cols-2">
      <label className="block text-sm font-semibold text-stone-800">First name<input name="firstName" required maxLength={100} autoComplete="given-name" defaultValue={firstName} className="mt-2 block w-full rounded-xl border border-stone-300 bg-stone-50 px-3 py-2.5 text-stone-900 focus:outline-none focus-visible:border-stone-500" /></label>
      <label className="block text-sm font-semibold text-stone-800">Last name<input name="lastName" required maxLength={100} autoComplete="family-name" defaultValue={lastName} className="mt-2 block w-full rounded-xl border border-stone-300 bg-stone-50 px-3 py-2.5 text-stone-900 focus:outline-none focus-visible:border-stone-500" /></label>
    </div>
    {email ? <label className="block text-sm font-semibold text-stone-800">Sign-in email<input readOnly value={email} className="mt-2 block w-full rounded-xl border border-stone-300 bg-stone-100 px-3 py-2.5 text-stone-700" /></label> : null}
    <label className="flex items-start gap-3 rounded-xl border border-stone-300 bg-stone-50 p-4 text-sm leading-6 text-stone-700"><input name="discoverable" type="checkbox" defaultChecked required className="mt-1 size-4 accent-emerald-800" /><span>Allow therapists to find my account by name or sign-in email. This does not grant access to clinical information; I become connected only when a therapist adds me.</span></label>
    <button disabled={busy} type="submit" className="cursor-grab rounded-xl bg-emerald-800 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-900 active:cursor-grabbing disabled:cursor-wait disabled:opacity-60">{busy ? "Creating account…" : "Complete client account"}</button>
    {error ? <p role="alert" className="text-sm text-red-700">{error}</p> : null}
  </form>;
}
