import Link from "next/link";

export function AppHeader() {
  return (
    <header className="border-b border-stone-200 bg-white">
      <div className="mx-auto flex h-16 w-[min(94vw,1200px)] items-center justify-between">
        <Link className="text-lg font-semibold tracking-tight text-stone-900" href="/">
          Therapist Dashboard
        </Link>
        <nav className="flex items-center gap-2" aria-label="Account navigation">
          <Link
            className="inline-flex items-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium text-stone-700 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"
            href="/settings"
          >
            <span aria-hidden="true">⚙</span>
            Account settings
          </Link>
          <Link
            className="rounded-md border border-stone-400 px-3.5 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"
            href="/onboarding/therapist"
          >
            Account
          </Link>
        </nav>
      </div>
    </header>
  );
}
