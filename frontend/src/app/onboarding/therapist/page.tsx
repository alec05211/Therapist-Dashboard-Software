import Link from "next/link";

import { TherapistOnboardingForm } from "@/components/onboarding/therapist-onboarding-form";
import { isAuth0Configured } from "@/lib/auth-config";
import { auth0 } from "@/lib/auth0";

export default async function TherapistOnboardingPage() {
  if (!isAuth0Configured) {
    return <Auth0SetupRequired />;
  }

  const session = await auth0.getSession();

  if (!session) {
    return <TherapistSignInRequired />;
  }

  return (
    <main className="mx-auto w-[min(92vw,760px)] py-12 sm:py-16">
      <p className="text-sm font-medium text-indigo-700">Practice setup</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-stone-950">
        Set up your therapist workspace
      </h1>
      <p className="mt-3 max-w-2xl text-base leading-7 text-stone-600">
        Start with your practice. You can later invite therapists and staff,
        then grant client-specific access only where it is appropriate.
      </p>
      <section className="mt-8 rounded-xl border border-stone-200 bg-white p-6 shadow-sm sm:p-8">
        <TherapistOnboardingForm
          email={typeof session.user.email === "string" ? session.user.email : undefined}
          suggestedName={typeof session.user.name === "string" ? session.user.name : undefined}
        />
      </section>
    </main>
  );
}

function TherapistSignInRequired() {
  return (
    <main className="mx-auto w-[min(92vw,680px)] py-16">
      <p className="text-sm font-medium text-indigo-700">Therapist onboarding</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-stone-950">
        Start your practice workspace
      </h1>
      <p className="mt-4 text-base leading-7 text-stone-600">
        Create your secure account first. After Auth0 verifies your identity,
        you&apos;ll set up your practice as an organization of one or a group practice.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <a
          className="rounded-md bg-stone-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-stone-700"
          href="/auth/login?screen_hint=signup&returnTo=/onboarding/therapist"
        >
          Create therapist account
        </a>
        <a
          className="rounded-md border border-stone-300 px-4 py-2.5 text-sm font-semibold text-stone-800 hover:bg-stone-50"
          href="/auth/login?returnTo=/onboarding/therapist"
        >
          Sign in
        </a>
      </div>
    </main>
  );
}

function Auth0SetupRequired() {
  return (
    <main className="mx-auto w-[min(92vw,680px)] py-16">
      <p className="text-sm font-medium text-amber-700">Configuration required</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-stone-950">
        Connect the development Auth0 tenant
      </h1>
      <p className="mt-4 text-base leading-7 text-stone-600">
        The onboarding experience is ready. Add the Auth0 development-tenant
        values to <code>frontend/.env.local</code>, then return here to create
        or sign in to a therapist account.
      </p>
      <Link
        className="mt-8 inline-flex rounded-md border border-stone-300 px-4 py-2.5 text-sm font-semibold text-stone-800 hover:bg-stone-50"
        href="/"
      >
        Return to the session workspace
      </Link>
    </main>
  );
}
