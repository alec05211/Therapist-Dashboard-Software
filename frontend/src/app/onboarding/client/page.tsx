import { ClientOnboardingForm } from "@/components/onboarding/client-onboarding-form";
import { isAuth0Configured } from "@/lib/auth-config";
import { auth0 } from "@/lib/auth0";

export default async function ClientOnboardingPage() {
  if (!isAuth0Configured) return <main className="mx-auto w-[min(92vw,680px)] py-16"><h1 className="text-2xl font-semibold text-stone-900">Account setup unavailable</h1><p className="mt-3 text-stone-600">Connect the development Auth0 tenant before creating a client account.</p></main>;
  const session = await auth0.getSession();
  if (!session) return <main className="mx-auto w-[min(92vw,680px)] py-16"><section className="rounded-2xl border border-stone-300 bg-white p-7 shadow-sm"><h1 className="text-2xl font-semibold text-stone-900">Create your client account</h1><p className="mt-3 text-sm leading-6 text-stone-600">Start with secure sign-in, then add the name therapists will use to find you.</p><div className="mt-6 flex gap-3"><a href="/auth/login?screen_hint=signup&returnTo=/onboarding/client" className="cursor-grab rounded-xl bg-emerald-800 px-4 py-2.5 text-sm font-semibold text-white active:cursor-grabbing">Create account</a><a href="/auth/login?returnTo=/onboarding/client" className="cursor-grab rounded-xl border border-stone-300 px-4 py-2.5 text-sm font-semibold text-stone-800 active:cursor-grabbing">Sign in</a></div></section></main>;
  const user = session.user as Record<string, unknown>;
  const profileName = typeof user.name === "string" && !user.name.includes("@") ? user.name : "";
  const fullName = profileName.trim().split(/\s+/).filter(Boolean);
  const firstName = typeof user.given_name === "string" ? user.given_name : fullName[0] || "";
  const lastName = typeof user.family_name === "string" ? user.family_name : fullName.slice(1).join(" ");
  const email = typeof user.email === "string" ? user.email : undefined;
  return <main className="mx-auto w-[min(92vw,680px)] py-12 sm:py-16"><header className="mb-7"><h1 className="text-3xl font-semibold tracking-tight text-stone-900">Complete your client account</h1><p className="mt-3 text-base leading-7 text-stone-600">Use the name your therapist should recognize.</p></header><ClientOnboardingForm firstName={firstName} lastName={lastName} email={email} /></main>;
}
