export function AppHeader() {
  return (
    <header className="border-b border-stone-200 bg-white">
      <div className="mx-auto flex h-16 w-[min(94vw,1200px)] items-center justify-between">
        <p className="text-lg font-semibold tracking-tight text-stone-900">
          Therapist Dashboard
        </p>
        <a
          className="rounded-md border border-stone-400 px-3.5 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50"
          href="/onboarding/therapist"
        >
          Account
        </a>
      </div>
    </header>
  );
}
