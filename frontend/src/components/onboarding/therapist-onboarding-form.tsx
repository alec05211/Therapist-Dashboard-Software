"use client";

import { FormEvent, useState } from "react";

type TherapistOnboardingFormProps = {
  email?: string;
  suggestedName?: string;
};

export function TherapistOnboardingForm({
  email,
  suggestedName,
}: TherapistOnboardingFormProps) {
  const [result, setResult] = useState<{ created: boolean; organizationName: string }>();
  const [error, setError] = useState<string>();
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);
    setIsSubmitting(true);

    const formData = new FormData(event.currentTarget);
    const response = await fetch("/api/onboarding/therapist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        organization_name: formData.get("organizationName"),
        professional_name: formData.get("professionalName"),
        practice_type: formData.get("practiceType"),
        team_setup: formData.get("teamSetup"),
      }),
    });
    const body = await response.json().catch(() => ({}));
    setIsSubmitting(false);

    if (!response.ok) {
      setError(body.detail || "Your practice could not be created. Please try again.");
      return;
    }

    setResult({
      created: Boolean(body.created),
      organizationName: String(body.organization_name || "your practice"),
    });
  }

  if (result) {
    return (
      <section className="rounded-xl border border-emerald-200 bg-emerald-50 p-6 text-emerald-950">
        <h2 className="text-lg font-semibold">
          {result.created ? "Your practice workspace is ready." : "Your practice workspace is already set up."}
        </h2>
        <p className="mt-2 text-sm leading-6">
          {result.organizationName} is now linked to your authenticated account.
          You can next invite therapists and staff, then grant client-specific
          access only where appropriate.
        </p>
      </section>
    );
  }

  return (
    <form className="space-y-8" onSubmit={submit}>
      <fieldset className="space-y-3">
        <legend className="text-base font-semibold text-stone-900">
          How are you starting?
        </legend>
        <p className="text-sm text-stone-600">
          Every practice is represented as an organization, including a solo
          practice.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="rounded-lg border border-stone-300 p-4 text-sm text-stone-800">
            <input className="mr-2" defaultChecked name="practiceType" type="radio" value="solo" />
            I&apos;m starting a solo practice
          </label>
          <label className="rounded-lg border border-stone-300 p-4 text-sm text-stone-800">
            <input className="mr-2" name="practiceType" type="radio" value="group" />
            I&apos;m setting up a group practice
          </label>
        </div>
      </fieldset>

      <div className="grid gap-5 sm:grid-cols-2">
        <label className="block text-sm font-medium text-stone-800">
          Practice name
          <input
            className="mt-2 block w-full rounded-md border border-stone-300 px-3 py-2 text-stone-900"
            name="organizationName"
            required
          />
        </label>
        <label className="block text-sm font-medium text-stone-800">
          Professional display name
          <input
            className="mt-2 block w-full rounded-md border border-stone-300 px-3 py-2 text-stone-900"
            defaultValue={suggestedName}
            name="professionalName"
            required
          />
        </label>
        <label className="block text-sm font-medium text-stone-800">
          Work email
          <input
            className="mt-2 block w-full rounded-md border border-stone-300 bg-stone-50 px-3 py-2 text-stone-700"
            defaultValue={email}
            name="email"
            readOnly
            type="email"
          />
        </label>
        <label className="block text-sm font-medium text-stone-800">
          Team setup
          <select
            className="mt-2 block w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-stone-900"
            defaultValue="later"
            name="teamSetup"
          >
            <option value="later">I&apos;ll invite people later</option>
            <option value="now">I plan to invite a team now</option>
          </select>
        </label>
      </div>

      <label className="flex gap-3 text-sm leading-6 text-stone-700">
        <input className="mt-1 size-4" required type="checkbox" />
        <span>
          I understand that organization membership does not automatically grant
          access to a client&apos;s clinical record. Client-specific therapist access
          will be granted separately and recorded in the audit trail.
        </span>
      </label>

      <button
        className="rounded-md bg-stone-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-stone-700 disabled:cursor-not-allowed disabled:opacity-60"
        disabled={isSubmitting}
        type="submit"
      >
        {isSubmitting ? "Creating secure workspace…" : "Create secure practice workspace"}
      </button>
      {error ? <p className="text-sm text-red-700" role="alert">{error}</p> : null}
    </form>
  );
}
