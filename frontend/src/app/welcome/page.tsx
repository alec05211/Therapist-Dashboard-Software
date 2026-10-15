import Link from "next/link";

export default function WelcomePage() {
  return <main className="mx-auto w-[min(92vw,760px)] py-12 sm:py-16">
    <section className="rounded-2xl border border-stone-200 bg-white p-7 shadow-sm sm:p-10">
      <p className="text-sm font-semibold uppercase tracking-[0.16em] text-emerald-800">Welcome</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-stone-900">Welcome to Therapist Dashboard</h1>
      <p className="mt-4 max-w-2xl text-sm leading-6 text-stone-600">Your secure sign-in is ready, but it is not connected to a therapist workspace or client profile yet. Choose how you use the product to finish setup.</p>
      <div className="mt-7 grid gap-3 sm:grid-cols-2">
        <Link href="/onboarding/therapist" className="cursor-grab rounded-xl border border-emerald-800 bg-emerald-800 p-4 text-white hover:bg-emerald-900 active:cursor-grabbing">
          <strong className="block text-sm">Set up a therapist workspace</strong><span className="mt-1 block text-xs text-emerald-100">Create your practice binding, then open Client list and Calendar.</span>
        </Link>
        <Link href="/settings?section=profile" className="cursor-grab rounded-xl border border-emerald-800 bg-emerald-800 p-4 text-white hover:bg-emerald-900 active:cursor-grabbing">
          <strong className="block text-sm">Set up a client profile</strong><span className="mt-1 block text-xs text-emerald-100">Add your full name, photo, and discovery preference.</span>
        </Link>
        <Link href="/inbox" className="cursor-grab rounded-xl border border-stone-300 bg-white p-4 text-stone-800 hover:bg-stone-50 active:cursor-grabbing sm:col-span-2">
          <strong className="block text-sm">Open inbox</strong><span className="mt-1 block text-xs text-stone-500">Review invitations and connection updates.</span>
        </Link>
      </div>
    </section>
  </main>;
}
