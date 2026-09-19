export function LoginLanding() {
  return (
    <main className="mx-auto flex min-h-[calc(100vh-4rem)] w-[min(92vw,760px)] items-center py-12">
      <section className="w-full rounded-2xl border border-stone-200 bg-white p-7 shadow-sm sm:p-10">
        <p className="text-sm font-semibold text-emerald-800">Therapist Dashboard</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-stone-900">Sign in securely.</h1>
        <p className="mt-3 max-w-xl text-base leading-7 text-stone-600">Your account determines whether you enter the therapist workspace or client portal. Passwords, verification, and sessions are handled by Auth0.</p>
        <div className="mt-8 grid gap-3 border-t border-stone-200 pt-6 sm:grid-cols-2">
          <a className="cursor-grab rounded-xl bg-emerald-800 px-4 py-3 text-center text-sm font-semibold text-white transition-colors duration-200 ease-out hover:bg-emerald-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing" href="/auth/login?returnTo=/">Sign in</a>
          <a className="cursor-grab rounded-xl border border-stone-300 px-4 py-3 text-center text-sm font-semibold text-stone-800 transition-colors duration-200 ease-out hover:bg-stone-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing" href="/auth/login?screen_hint=signup&returnTo=/">Create an account</a>
        </div>
        <p className="mt-5 text-xs leading-5 text-stone-500">Creating an identity does not create a practice. Practice setup is a separate, authenticated workflow. For synthetic demonstration accounts only.</p>
      </section>
    </main>
  );
}
