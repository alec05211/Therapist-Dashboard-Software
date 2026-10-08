import Link from "next/link";

function ArrowIcon() {
  return (
    <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14m-5-5 5 5-5 5" />
    </svg>
  );
}

function SparkIcon() {
  return (
    <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.6">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3.75 13.75 9 19 10.75 13.75 12.5 12 17.75 10.25 12.5 5 10.75 10.25 9 12 3.75Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="m18.25 16.25.75 2.25 2.25.75-2.25.75-.75 2.25-.75-2.25-2.25-.75 2.25-.75.75-2.25Z" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.7">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v3m10.5-3v3M4.5 9.75h15M5.75 4.5h12.5c.69 0 1.25.56 1.25 1.25v12.5c0 .69-.56 1.25-1.25 1.25H5.75c-.69 0-1.25-.56-1.25-1.25V5.75c0-.69.56-1.25 1.25-1.25Z" />
    </svg>
  );
}

function ClaimIcon() {
  return (
    <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.7">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3.75h10.5c.83 0 1.5.67 1.5 1.5v13.5c0 .83-.67 1.5-1.5 1.5H6.75c-.83 0-1.5-.67-1.5-1.5V5.25c0-.83.67-1.5 1.5-1.5Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 8.25h7.5m-7.5 3h7.5m-7.5 3h4.5" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.7">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3.75 19 6v5.25c0 4.2-2.9 7.68-7 9-4.1-1.32-7-4.8-7-9V6l7-2.25Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="m9.25 12 1.75 1.75 3.75-4" />
    </svg>
  );
}

function InsightPreview() {
  return (
    <div className="relative mx-auto w-full max-w-[620px]" aria-label="Illustration of the longitudinal Insights workspace">
      <div className="absolute -left-8 top-12 hidden h-28 w-28 rounded-full border border-[var(--border)] bg-[var(--accent-surface)] lg:block" />
      <div className="absolute -bottom-7 -right-5 hidden h-24 w-24 rounded-[2rem] border border-[var(--border)] bg-[var(--surface-inset)] lg:block" />
      <div className="relative overflow-hidden rounded-[1.75rem] border border-[var(--border-strong)] bg-[var(--surface)] p-3 shadow-[0_24px_70px_rgba(41,37,36,0.14)] sm:p-4">
        <div className="flex items-center justify-between rounded-2xl border border-[var(--border)] bg-[var(--surface-subtle)] px-4 py-3">
          <div className="flex items-center gap-2.5">
            <span className="grid size-8 place-items-center rounded-full bg-[var(--accent-strong)] text-xs font-semibold text-white">ER</span>
            <div>
              <p className="text-xs font-semibold text-stone-900">Elena&apos;s clinical journey</p>
              <p className="mt-0.5 text-[10px] text-stone-500">6 finalized sessions</p>
            </div>
          </div>
          <span className="rounded-full border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-[10px] font-semibold text-emerald-800">Insights</span>
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-[0.82fr_1.18fr]">
          <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-subtle)] p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-stone-500">Journey map</p>
            <div className="relative mt-4 space-y-4 pl-5 before:absolute before:bottom-1 before:left-[5px] before:top-1 before:w-px before:bg-[var(--border-strong)]">
              {[
                ["May 8", "Naming the pressure cycle"],
                ["May 22", "Making room for rest"],
                ["Jun 5", "Practicing clear requests"],
              ].map(([date, title], index) => (
                <div className="relative" key={date}>
                  <span className={`absolute -left-5 top-1 size-2.5 rounded-full border-2 ${index === 2 ? "border-[var(--accent-strong)] bg-[var(--accent-strong)]" : "border-[var(--border-strong)] bg-[var(--surface-subtle)]"}`} />
                  <p className="text-[9px] font-medium text-stone-500">{date}</p>
                  <p className="mt-0.5 text-[11px] font-semibold leading-4 text-stone-800">{title}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface-subtle)] p-4">
            <div className="flex items-center gap-2 text-emerald-800">
              <SparkIcon />
              <p className="text-xs font-semibold">Clinical overview</p>
            </div>
            <p className="mt-3 text-[11px] leading-[1.65] text-stone-700">
              Across recent sessions, Elena may be moving from recognizing an over-responsibility pattern toward testing clearer requests and protected rest.
            </p>
            <div className="mt-4 grid gap-2">
              <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3">
                <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-stone-500">Change over time</p>
                <p className="mt-1.5 text-[10px] leading-4 text-stone-700">More specific language around needs and boundaries appears in the last two sessions.</p>
              </div>
              <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3">
                <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-stone-500">Open thread</p>
                <p className="mt-1.5 text-[10px] leading-4 text-stone-700">Review how the planned conversation at work affected the pressure cycle.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-3 flex items-center justify-between rounded-xl bg-[var(--surface-inset)] px-4 py-2.5 text-[10px] text-stone-600">
          <span>Grounded in therapist-finalized records</span>
          <span className="font-semibold text-emerald-800">View cited evidence</span>
        </div>
      </div>
    </div>
  );
}

export function PublicLanding() {
  return (
    <main className="overflow-hidden">
      <section className="relative isolate border-b border-[var(--border)] px-4 py-16 sm:px-6 sm:py-24 lg:py-28">
        <div className="absolute inset-x-0 top-0 -z-10 h-[68%] bg-[radial-gradient(circle_at_16%_18%,var(--accent-surface),transparent_35%),radial-gradient(circle_at_82%_22%,var(--surface-inset),transparent_32%)] opacity-80" />
        <div className="mx-auto grid w-full max-w-[1240px] items-center gap-14 lg:grid-cols-[0.9fr_1.1fr] lg:gap-16">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-800">
              <SparkIcon />
              Longitudinal mental health synthesis
            </p>
            <h1 className="mt-7 max-w-[680px] text-5xl font-semibold leading-[0.98] tracking-[-0.045em] text-stone-900 sm:text-6xl lg:text-[4.6rem]">
              Every session adds to a clearer story.
            </h1>
            <p className="mt-7 max-w-[600px] text-lg leading-8 text-stone-600 sm:text-xl">
              Therapist Sidekick helps clinicians connect themes, changes, and open threads across the course of care—then brings scheduling, billing, and insurance into the same calm workspace.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <a className="inline-flex cursor-grab items-center justify-center gap-2 rounded-xl bg-emerald-800 px-5 py-3.5 text-sm font-semibold text-white transition-colors duration-200 ease-out hover:bg-emerald-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing" href="#longitudinal-insights">
                See how the journey comes together
                <ArrowIcon />
              </a>
              <Link className="inline-flex cursor-grab items-center justify-center rounded-xl border border-stone-300 bg-white px-5 py-3.5 text-sm font-semibold text-stone-800 transition-colors duration-200 ease-out hover:bg-stone-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing" href="/login">
                Sign in to your workspace
              </Link>
            </div>
            <p className="mt-5 flex max-w-xl items-start gap-2 text-xs leading-5 text-stone-500">
              <ShieldIcon />
              AI-assisted insights support clinical review. Therapists remain in control of interpretation and care decisions.
            </p>
          </div>
          <InsightPreview />
        </div>
      </section>

      <section id="longitudinal-insights" className="scroll-mt-8 px-4 py-20 sm:px-6 sm:py-28">
        <div className="mx-auto w-full max-w-[1120px]">
          <div className="mx-auto max-w-[760px] text-center">
            <p className="text-sm font-semibold text-emerald-800">The clinical journey, made reviewable</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-stone-900 sm:text-5xl">See what changes between the sessions.</h2>
            <p className="mt-5 text-base leading-7 text-stone-600 sm:text-lg">
              Move beyond isolated notes. Therapist-controlled synthesis organizes the history of care into useful context while keeping the source record close at hand.
            </p>
          </div>

          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {[
              ["01", "Follow the trajectory", "Review meaningful changes, recurring themes, and unresolved threads across finalized sessions."],
              ["02", "Stay close to the evidence", "Trace important statements back to their source session, transcript, and recording context."],
              ["03", "Keep the clinician in control", "Correct, dismiss, pin, or mark context outdated so future synthesis reflects clinical judgment."],
            ].map(([number, title, body]) => (
              <article className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-sm" key={number}>
                <span className="text-sm font-semibold text-emerald-800">{number}</span>
                <h3 className="mt-8 text-xl font-semibold tracking-tight text-stone-900">{title}</h3>
                <p className="mt-3 text-sm leading-6 text-stone-600">{body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="border-y border-[var(--border)] bg-[var(--surface)] px-4 py-20 sm:px-6 sm:py-28">
        <div className="mx-auto grid w-full max-w-[1120px] gap-12 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
          <div>
            <p className="text-sm font-semibold text-emerald-800">One connected practice</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.035em] text-stone-900 sm:text-5xl">Care and operations should share the same rhythm.</h2>
            <p className="mt-5 text-base leading-7 text-stone-600">
              The work around a session should not live in disconnected systems. Bring the clinical workflow and the practical work of running a practice together.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            {[
              [<CalendarIcon key="calendar" />, "Scheduling", "Keep availability, recurring appointments, and session preparation connected."],
              [<ClaimIcon key="billing" />, "Billing", "Move from completed care to clear, organized billing workflows."],
              [<ShieldIcon key="insurance" />, "Insurance", "Keep coverage and claims work alongside the client and session context it supports."],
            ].map(([icon, title, body]) => (
              <article className="rounded-2xl border border-[var(--border)] bg-[var(--surface-subtle)] p-5" key={String(title)}>
                <span className="grid size-10 place-items-center rounded-xl bg-emerald-50 text-emerald-800">{icon}</span>
                <h3 className="mt-6 text-lg font-semibold text-stone-900">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-stone-600">{body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="px-4 py-20 sm:px-6 sm:py-28">
        <div className="mx-auto max-w-[1120px] overflow-hidden rounded-[2rem] border border-[var(--border-strong)] bg-[var(--accent-strong)] px-6 py-12 text-center text-white shadow-[0_22px_60px_rgba(41,37,36,0.16)] sm:px-12 sm:py-16">
          <p className="text-sm font-semibold text-white/75">A more connected view of care</p>
          <h2 className="mx-auto mt-4 max-w-[760px] text-3xl font-semibold tracking-[-0.035em] sm:text-5xl">Hold onto the thread without losing the human story.</h2>
          <p className="mx-auto mt-5 max-w-[640px] text-sm leading-6 text-white/80 sm:text-base">
            A private, clinician-guided workspace for understanding the journey and managing what comes next.
          </p>
          <Link className="mt-8 inline-flex cursor-grab items-center justify-center gap-2 rounded-xl bg-white px-5 py-3.5 text-sm font-semibold text-emerald-900 transition-colors duration-200 ease-out hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white active:cursor-grabbing" href="/login">
            Open your workspace
            <ArrowIcon />
          </Link>
        </div>
      </section>

      <footer className="border-t border-[var(--border)] px-4 py-8 sm:px-6">
        <div className="mx-auto flex w-full max-w-[1120px] flex-col gap-2 text-xs text-stone-500 sm:flex-row sm:items-center sm:justify-between">
          <p className="font-semibold text-stone-700">Therapist Sidekick</p>
          <p>Clinical support, not clinical replacement.</p>
        </div>
      </footer>
    </main>
  );
}
