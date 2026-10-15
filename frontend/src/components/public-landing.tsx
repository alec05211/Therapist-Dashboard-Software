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

function ConversationIcon() {
  return (
    <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.7">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 5.75c0-.69.56-1.25 1.25-1.25h12.5c.69 0 1.25.56 1.25 1.25v8.5c0 .69-.56 1.25-1.25 1.25h-7l-4.75 3v-3h-.75c-.69 0-1.25-.56-1.25-1.25v-8.5Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 8.5h7.5m-7.5 3h4.5" />
    </svg>
  );
}

function DocumentIcon() {
  return (
    <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.7">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3.75h7.5l3 3v13.5H6.75V3.75Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.25 3.75v3h3M9 11.25h6m-6 3h4.5m-4.5 3h2.25" />
    </svg>
  );
}

function JourneyIcon() {
  return (
    <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.7">
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 5.25a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Zm14.5 13.5a2.25 2.25 0 1 1-4.5 0 2.25 2.25 0 0 1 4.5 0Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.75 7.5v2.25A3.25 3.25 0 0 0 8 13h8a3 3 0 0 1 3 3v.5M9.25 9.75 12 13l-2.75 3.25" />
    </svg>
  );
}

function WaveMark({ className = "" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} fill="none" viewBox="0 0 120 28">
      <path d="M2 16c13 0 13-9 26-9s13 14 26 14S67 5 80 5s13 11 25 11c6 0 10-2 13-5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
    </svg>
  );
}

type ThreadDirection = "right-left" | "left-left" | "left-right" | "right-right" | "right-center" | "left-center" | "center-center";

type BraidTension = "wide" | "tight";

type ThreadRoute = "upper" | "middle" | "lower";

function ThreadSegment({ direction, braid, route = "middle" }: { direction: ThreadDirection; braid?: BraidTension; route?: ThreadRoute }) {
  // Every path begins and ends with a vertical tangent. Adjacent sections share
  // both their endpoint and tangent, so the thread remains C1-continuous.
  const crossPaths: Record<ThreadRoute, Pick<Record<ThreadDirection, string>, "right-left" | "left-right">> = {
    upper: {
      "right-left": "M88 0 C88 10 85 18 78 24 C66 34 50 38 34 42 C20 46 11 58 10 72 C9 82 10 94 10 100",
      "left-right": "M10 0 C10 10 13 18 20 24 C32 34 48 38 64 42 C78 46 87 58 88 72 C89 82 88 94 88 100",
    },
    middle: {
      "right-left": "M88 0 C88 18 90 36 84 44 C76 51 60 53 43 53 C28 53 17 54 12 58 C9 64 10 90 10 100",
      "left-right": "M10 0 C10 18 8 36 14 44 C22 51 38 53 55 53 C70 53 81 54 86 58 C89 64 88 90 88 100",
    },
    lower: {
      "right-left": "M88 0 C88 22 91 43 88 58 C85 72 72 78 56 81 C38 84 18 84 12 90 C10 93 10 97 10 100",
      "left-right": "M10 0 C10 22 7 43 10 58 C13 72 26 78 42 81 C60 84 80 84 86 90 C88 93 88 97 88 100",
    },
  };
  const paths: Record<ThreadDirection, string> = {
    ...crossPaths[route],
    "left-left": "M10 0 C10 14 16 27 14 40 C12 54 5 68 7 80 C9 89 10 95 10 100",
    "right-right": "M88 0 C88 14 82 27 84 40 C86 54 93 68 91 80 C89 89 88 95 88 100",
    "right-center": "M88 0 C88 18 90 32 86 43 C81 56 67 67 55 78 C51 84 50 94 50 100",
    "left-center": "M10 0 C10 18 8 32 12 43 C17 56 31 67 43 78 C49 84 50 94 50 100",
    "center-center": "M50 0 C50 14 55 27 53 40 C51 54 46 68 48 80 C50 89 50 95 50 100",
  };
  const braidPaths: Record<BraidTension, Partial<Record<ThreadDirection, string[]>>> = {
    wide: {
      "right-right": [
        "M88 0 C88 15 84 27 83 40 C82 55 88 68 89 81 C89 89 88 95 88 100",
        "M88 0 C88 15 92 27 93 40 C94 55 88 68 87 81 C87 89 88 95 88 100",
      ],
    },
    tight: {
      "right-right": [
        "M88 0 C88 15 86 28 86 41 C86 55 89 69 89 81 C89 89 88 95 88 100",
        "M88 0 C88 15 90 28 90 41 C90 55 87 69 87 81 C87 89 88 95 88 100",
      ],
    },
  };

  return (
    <svg aria-hidden="true" className="pointer-events-none absolute inset-0 z-0 hidden size-full text-[var(--border-strong)] md:block" preserveAspectRatio="none" viewBox="0 0 100 100">
      <path d={paths[direction]} fill="none" opacity="0.5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.4" vectorEffect="non-scaling-stroke" />
      {braid && braidPaths[braid][direction]?.map((path) => <path d={path} fill="none" key={path} opacity="0.23" stroke="currentColor" strokeLinecap="round" strokeWidth="1" vectorEffect="non-scaling-stroke" />)}
    </svg>
  );
}

function FlowIcon({ kind }: { kind: "capture" | "review" | "finalize" | "synthesize" | "prepare" }) {
  const paths = {
    capture: <><path d="M12 3.75a3 3 0 0 0-3 3v4.5a3 3 0 0 0 6 0v-4.5a3 3 0 0 0-3-3Z" /><path d="M5.75 10.75v.5a6.25 6.25 0 0 0 12.5 0v-.5M12 17.5v2.75m-3 0h6" /></>,
    review: <><path d="M5.25 4.5h13.5v15H5.25z" /><path d="M8.25 8.25h7.5m-7.5 3h5.5m-5.5 3h3.5" /></>,
    finalize: <><path d="M12 3.75 19 6v5.25c0 4.2-2.9 7.68-7 9-4.1-1.32-7-4.8-7-9V6l7-2.25Z" /><path d="m9 12 2 2 4-5" /></>,
    synthesize: <><path d="M12 3.5 13.6 8.4 18.5 10l-4.9 1.6-1.6 4.9-1.6-4.9L5.5 10l4.9-1.6L12 3.5Z" /><path d="m18.5 15 .7 2.1 2.1.7-2.1.7-.7 2.1-.7-2.1-2.1-.7 2.1-.7.7-2.1Z" /></>,
    prepare: <><path d="M6.25 4.5h11.5c.69 0 1.25.56 1.25 1.25v12.5c0 .69-.56 1.25-1.25 1.25H6.25c-.69 0-1.25-.56-1.25-1.25V5.75c0-.69.56-1.25 1.25-1.25Z" /><path d="M8 2.75v3.5m8-3.5v3.5M5 9h14m-8 3 1.5 1.5L16 10" /></>,
  };
  return <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6">{paths[kind]}</svg>;
}

function CareFlow() {
  const steps = [
    { kind: "capture" as const, title: "Capture", body: "Preserve the conversation—with timing, speakers, and tone still within reach." },
    { kind: "review" as const, title: "Review", body: "Correct the transcript and shape the draft note while the session is still fresh." },
    { kind: "finalize" as const, title: "Finalize", body: "Establish the therapist-reviewed record that later context can trust." },
    { kind: "synthesize" as const, title: "Synthesize", body: "Bring possible changes, recurring themes, and open threads into view." },
    { kind: "prepare" as const, title: "Prepare", body: "Return only the context that may matter for the conversation ahead." },
  ];
  const offsets = ["lg:mt-10", "lg:mt-24", "lg:mt-4", "lg:mt-20", "lg:mt-10"];

  return (
    <div className="relative mt-14 lg:mt-16">
      <div aria-hidden="true" className="absolute bottom-7 left-[21px] top-7 w-px bg-[var(--border-strong)] lg:hidden" />
      <div className="grid lg:min-h-[330px] lg:grid-cols-5 lg:gap-0">
        {steps.map((step, index) => (
          <article className={`relative grid grid-cols-[auto_1fr] gap-4 border-b border-[var(--border)] py-5 last:border-b-0 lg:block lg:border-0 lg:px-5 lg:py-0 lg:text-center ${offsets[index]}`} key={step.title}>
            <span className="relative z-10 grid size-11 shrink-0 place-items-center rounded-full border border-[var(--border-strong)] bg-[var(--surface)] text-[var(--accent-text)] shadow-sm lg:mx-auto">
              <FlowIcon kind={step.kind} />
            </span>
            <div className="lg:mt-5">
              <h3 className="text-base font-semibold text-stone-900">{step.title}</h3>
              <p className="mt-2 text-sm leading-6 text-stone-600">{step.body}</p>
            </div>
          </article>
        ))}
      </div>
      <div className="mx-auto mt-4 flex max-w-3xl items-center gap-4 text-[11px] font-semibold uppercase tracking-[0.16em] text-stone-500 lg:mt-0">
        <span>Faithful record</span>
        <span className="h-px flex-1 bg-[linear-gradient(to_right,var(--border-strong),var(--accent-strong))]" />
        <span className="text-[var(--accent-text)]">Useful context</span>
      </div>
    </div>
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
      <section className="relative isolate flex min-h-[calc(100svh-4rem)] items-center border-b border-[var(--border)] px-4 py-16 sm:px-6 sm:py-20">
        <div className="absolute inset-x-0 top-0 -z-10 h-[68%] bg-[radial-gradient(circle_at_16%_18%,var(--accent-surface),transparent_35%),radial-gradient(circle_at_82%_22%,var(--surface-inset),transparent_32%)] opacity-80" />
        <div aria-hidden="true" className="absolute -right-24 bottom-10 -z-10 size-80 rounded-full border border-[var(--border)] opacity-50 sm:size-[30rem]" />
        <ThreadSegment braid="wide" direction="right-right" />
        <div className="relative z-10 mx-auto grid w-full max-w-[1240px] items-center gap-14 lg:grid-cols-[0.9fr_1.1fr] lg:gap-16">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-800">
              <SparkIcon />
              Longitudinal mental health synthesis
            </p>
            <h1 className="mt-7 max-w-[680px] text-5xl font-semibold leading-[0.98] tracking-[-0.045em] text-stone-900 sm:text-6xl lg:text-[4.6rem]">
              See the full course of care. Carry the right context forward.
            </h1>
            <p className="mt-7 max-w-[600px] text-lg leading-8 text-stone-600 sm:text-xl">
              A longitudinal care workspace that helps mental health professionals understand the clinical journey across sessions—and manage the practice around it, from scheduling and coordination to billing, insurance, documents, and consent.
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

      <section className="relative isolate flex min-h-[85svh] items-center overflow-hidden px-4 py-20 sm:min-h-[calc(100svh-4rem)] sm:px-6 sm:py-24">
        <ThreadSegment direction="right-left" route="middle" />
        <div className="relative z-10 mx-auto w-full max-w-[1180px]">
          <div className="grid gap-8 lg:grid-cols-[0.42fr_1.58fr] lg:items-end lg:gap-16">
            <div className="max-w-xs text-[var(--accent-text)]">
              <WaveMark className="w-28" />
              <p className="mt-5 text-sm font-semibold">The work between the words</p>
            </div>
            <h2 className="max-w-[900px] text-balance text-4xl font-semibold tracking-[-0.045em] text-stone-900 sm:text-6xl">A full caseload asks a great deal of human memory.</h2>
          </div>
          <div className="mt-14 grid gap-8 border-t border-[var(--border)] pt-8 md:grid-cols-2 lg:ml-[28%] lg:gap-14">
            <p className="max-w-xl text-lg leading-8 text-stone-600 sm:text-xl">
              Good therapy depends on continuity: remembering what carried weight, what changed, what remains unresolved, and how today connects to months of earlier work.
            </p>
            <p className="max-w-xl text-lg leading-8 text-stone-600 sm:text-xl">
              Every client has a distinct history, language, relationships, goals, and pace. Holding many evolving stories at once asks a great deal of human attention.
            </p>
          </div>
        </div>
      </section>

      <section className="relative isolate flex min-h-[85svh] items-center overflow-hidden border-y border-[var(--border)] bg-[var(--surface)] px-4 py-20 sm:min-h-[calc(100svh-4rem)] sm:px-6 sm:py-24">
        <ThreadSegment direction="left-left" />
        <div className="relative z-10 mx-auto w-full max-w-[1180px]">
          <div className="grid gap-8 lg:grid-cols-[0.45fr_1.55fr] lg:items-end lg:gap-16">
            <div>
              <p className="text-sm font-semibold text-emerald-800">Continuity is the challenge</p>
              <WaveMark className="mt-6 w-36 text-[var(--border-strong)]" />
            </div>
            <h2 className="max-w-[900px] text-balance text-4xl font-semibold tracking-[-0.045em] text-stone-900 sm:text-6xl">The details accumulate. Their meaning keeps changing.</h2>
          </div>
          <div className="mt-14 grid gap-px overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--border)] md:grid-cols-3">
              {[
                ["Across the record", "Important context lives across sessions, finalized notes, transcript moments, documents, and clinician observations."],
                ["Across time", "A concern raised once, a recurring theme, and a meaningful change in direction are not the same kind of signal."],
                ["Around the session", "Preparation, documentation, scheduling, messages, forms, billing, and reimbursement all compete for attention."],
              ].map(([title, body]) => (
                <article className="bg-[var(--surface-subtle)] p-6 lg:min-h-44 lg:p-7" key={title}>
                  <h3 className="text-base font-semibold text-stone-900">{title}</h3>
                  <p className="mt-4 max-w-sm text-sm leading-6 text-stone-600">{body}</p>
                </article>
              ))}
          </div>
        </div>
      </section>

      <section className="relative isolate flex min-h-[85svh] items-center overflow-hidden px-4 py-20 sm:min-h-[calc(100svh-4rem)] sm:px-6 sm:py-24">
        <ThreadSegment direction="left-right" route="middle" />
        <div className="relative z-10 mx-auto w-full max-w-[1120px]">
          <p className="text-sm font-semibold text-emerald-800">A gentler kind of support</p>
          <div className="mt-5 grid gap-12 lg:grid-cols-[1.1fr_0.9fr] lg:items-end lg:gap-20">
            <h2 className="text-4xl font-semibold tracking-[-0.045em] text-stone-900 sm:text-6xl">Not a substitute for memory. A way to return prepared.</h2>
            <p className="text-lg leading-8 text-stone-600 sm:text-xl">
              The product keeps relevant history, possible patterns, open threads, and supporting evidence close enough to review—so the therapist can spend less time reconstructing and more attention with the person in the room.
            </p>
          </div>
          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {[
              ["Return oriented", "Bring forward what may matter for the next conversation, not an indiscriminate dossier."],
              ["Relationship specific", "Preserve the language, history, and pace of one therapist-client relationship."],
              ["Clinician guided", "Let professional judgment decide what is useful, incomplete, outdated, or wrong."],
            ].map(([title, body]) => (
              <article className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-sm" key={title}>
                <h3 className="text-xl font-semibold tracking-tight text-stone-900">{title}</h3>
                <p className="mt-3 text-sm leading-6 text-stone-600">{body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="longitudinal-insights" className="relative isolate flex min-h-[85svh] scroll-mt-8 items-center overflow-hidden border-y border-[var(--border)] bg-[var(--surface)] px-4 py-20 sm:min-h-[calc(100svh-4rem)] sm:px-6 sm:py-24">
        <ThreadSegment direction="right-left" route="lower" />
        <div className="relative z-10 mx-auto grid w-full max-w-[1180px] gap-14 lg:grid-cols-[0.82fr_1.18fr] lg:items-center lg:gap-20">
          <div>
            <p className="text-sm font-semibold text-emerald-800">The clinical journey, made visible</p>
            <h2 className="mt-5 text-4xl font-semibold tracking-[-0.045em] text-stone-900 sm:text-6xl">See what changes between the sessions.</h2>
            <p className="mt-6 text-lg leading-8 text-stone-600">
              Therapist-controlled synthesis turns a collection of finalized sessions into a reviewable clinical journey: meaningful changes, recurring themes, relevant context, and open threads.
            </p>
          </div>
          <InsightPreview />
        </div>
      </section>

      <section id="care-flow" className="relative flex min-h-[85svh] scroll-mt-8 items-center overflow-hidden px-4 py-20 sm:min-h-[calc(100svh-4rem)] sm:px-6 sm:py-24">
        <div aria-hidden="true" className="absolute -left-40 top-1/2 size-[30rem] -translate-y-1/2 rounded-full bg-[radial-gradient(circle,var(--accent-surface),transparent_68%)] opacity-70" />
        <svg aria-hidden="true" className="pointer-events-none absolute inset-0 z-0 hidden size-full text-[var(--border-strong)] lg:block" preserveAspectRatio="none" viewBox="0 0 1000 900">
          <path d="M100 0 C100 84 82 132 108 205 C132 272 112 328 98 382 C88 421 106 475 165 475 C242 475 274 535 330 535 C397 535 423 455 495 455 C566 455 590 520 660 520 C733 520 760 475 825 475 C918 475 934 574 895 668 C862 748 880 814 880 900" fill="none" opacity="0.5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.4" vectorEffect="non-scaling-stroke" />
        </svg>
        <div className="relative z-10 mx-auto w-full max-w-[1180px]">
          <div className="grid gap-8 lg:grid-cols-[1.3fr_0.7fr] lg:items-end lg:gap-20">
            <div>
              <p className="text-sm font-semibold text-emerald-800">From session to useful context</p>
              <h2 className="mt-5 max-w-[860px] text-4xl font-semibold tracking-[-0.045em] text-stone-900 sm:text-6xl">A record becomes useful through review—not accumulation alone.</h2>
            </div>
            <p className="max-w-md text-base leading-7 text-stone-600 lg:pb-2">Each step adds judgment, structure, and restraint. The result is not more information—it is a clearer way back into the work.</p>
          </div>
          <CareFlow />
        </div>
      </section>

      <section className="relative isolate flex min-h-[85svh] items-center overflow-hidden border-y border-[var(--border)] bg-[var(--surface)] px-4 py-20 sm:min-h-[calc(100svh-4rem)] sm:px-6 sm:py-24">
        <ThreadSegment braid="tight" direction="right-right" />
        <div className="relative z-10 mx-auto w-full max-w-[1240px]">
          <div className="grid gap-8 lg:grid-cols-[1.35fr_0.65fr] lg:items-end lg:gap-20">
            <div>
              <p className="text-sm font-semibold text-emerald-800">Trust is part of the interface</p>
              <h2 className="mt-5 text-balance text-4xl font-semibold tracking-[-0.045em] text-stone-900 sm:text-6xl">Useful because it stays reviewable.</h2>
            </div>
            <p className="max-w-md text-lg leading-8 text-stone-600">
              AI-assisted context should offer a place to look—not declare what is clinically true.
            </p>
          </div>
          <div className="mt-14 grid gap-px overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["Finalized records first", "Longitudinal context is grounded in therapist-reviewed source material."],
              ["Evidence stays close", "Important statements can be traced to the relevant session, transcript, and recording context."],
              ["Corrections carry forward", "Therapists can correct, dismiss, pin, or mark remembered context outdated."],
              ["Judgment stays human", "The system supports review; it does not diagnose, determine risk, or make treatment decisions."],
            ].map(([title, body]) => (
              <article className="bg-[var(--surface-subtle)] p-5 lg:min-h-56 lg:p-6" key={title}>
                <span className="grid size-9 place-items-center rounded-xl bg-emerald-50 text-emerald-800"><ShieldIcon /></span>
                <h3 className="mt-7 text-base font-semibold text-stone-900">{title}</h3>
                <p className="mt-3 text-sm leading-6 text-stone-600">{body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="relative isolate flex min-h-[85svh] items-center overflow-hidden px-4 py-20 sm:min-h-[calc(100svh-4rem)] sm:px-6 sm:py-24">
        <ThreadSegment direction="right-left" route="middle" />
        <div className="relative z-10 mx-auto w-full max-w-[1240px]">
          <div className="grid gap-8 lg:grid-cols-[1.1fr_0.7fr_0.7fr] lg:items-end lg:gap-12">
            <div>
              <p className="text-sm font-semibold text-emerald-800">One connected practice</p>
              <h2 className="mt-5 text-balance text-3xl font-semibold tracking-[-0.035em] text-stone-900 sm:text-5xl">The clinical journey and the work around it belong together.</h2>
            </div>
            <p className="border-t border-[var(--border)] pt-5 text-base leading-7 text-stone-600">
              Context weakens when the session record, preparation, messages, calendars, and files live in separate systems.
            </p>
            <p className="border-t border-[var(--border)] pt-5 text-base leading-7 text-stone-600">
              The platform brings those responsibilities back into one coherent client relationship.
            </p>
          </div>

          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {[
              [<JourneyIcon key="journey" />, "Clinical journey", "Review longitudinal synthesis, changes over time, recurring themes, open threads, and the evidence behind them."],
              [<SparkIcon key="sessions" />, "Sessions and preparation", "Move from secure capture and transcript review to finalized notes and selective pre-session context."],
              [<CalendarIcon key="calendar" />, "Scheduling", "Coordinate availability, recurring appointments, session changes, and preparation around the same client relationship."],
            ].map(([icon, title, body]) => (
              <article className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-sm" key={String(title)}>
                <span className="grid size-10 place-items-center rounded-xl bg-emerald-50 text-emerald-800">{icon}</span>
                <h3 className="mt-7 text-lg font-semibold text-stone-900">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-stone-600">{body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="relative isolate flex min-h-[85svh] items-center overflow-hidden border-y border-[var(--border)] bg-[var(--surface)] px-4 py-20 sm:min-h-[calc(100svh-4rem)] sm:px-6 sm:py-24">
        <ThreadSegment direction="left-left" />
        <div className="relative z-10 mx-auto w-full max-w-[1240px]">
          <div className="grid gap-8 lg:grid-cols-[1.35fr_0.65fr] lg:items-end lg:gap-20">
            <div>
              <p className="text-sm font-semibold text-emerald-800">The practice around care</p>
              <h2 className="mt-5 text-balance text-4xl font-semibold tracking-[-0.045em] text-stone-900 sm:text-6xl">Fewer handoffs between care and administration.</h2>
            </div>
            <p className="max-w-md text-lg leading-8 text-stone-600">The operational record stays connected to the same client relationship instead of becoming a second, fragmented story.</p>
          </div>
          <div className="mt-14 grid gap-px overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-4">
            {[
              [<ClaimIcon key="billing" />, "Billing and insurance", "Organize coverage, claims, reimbursement, and completed-care workflows."],
              [<ConversationIcon key="chat" />, "Care coordination", "Keep appropriate client communication, reminders, and practice coordination together."],
              [<DocumentIcon key="documents" />, "Documents and consent", "Share, review, sign, and retain practice documents and consent forms."],
              [<CalendarIcon key="calendar" />, "A shared timeline", "See clinical and practice activity as parts of one continuing relationship."],
            ].map(([icon, title, body]) => (
              <article className="bg-[var(--surface-subtle)] p-5 lg:min-h-52 lg:p-6" key={String(title)}>
                <span className="grid size-10 place-items-center rounded-xl bg-emerald-50 text-emerald-800">{icon}</span>
                <h3 className="mt-7 text-base font-semibold text-stone-900">{title}</h3>
                <p className="mt-3 text-sm leading-6 text-stone-600">{body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="relative isolate flex min-h-[85svh] items-center overflow-hidden px-4 py-20 sm:min-h-[calc(100svh-4rem)] sm:px-6 sm:py-24">
        <ThreadSegment direction="left-center" />
        <div className="relative z-10 mx-auto w-full max-w-[1120px]">
          <p className="text-sm font-semibold text-emerald-800">Built for the people carrying the work</p>
          <h2 className="mt-5 max-w-[860px] text-4xl font-semibold tracking-[-0.045em] text-stone-900 sm:text-6xl">A calmer workspace for practices that cannot afford to lose the thread.</h2>
          <div className="mt-12 grid gap-4 md:grid-cols-3">
            {[
              ["Solo practitioners", "A single place to move from the clinical conversation to preparation and practice administration."],
              ["Group practices", "A coherent foundation for organizing care relationships, workflows, and appropriately managed access."],
              ["Clients", "Clearer coordination around appointments, communication, documents, and permitted participation in their care journey."],
            ].map(([title, body]) => (
              <article className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6 shadow-sm" key={title}>
                <h3 className="text-xl font-semibold text-stone-900">{title}</h3>
                <p className="mt-3 text-sm leading-6 text-stone-600">{body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="relative isolate flex min-h-[85svh] items-center overflow-hidden px-4 py-20 sm:min-h-[calc(100svh-4rem)] sm:px-6 sm:py-24">
        <ThreadSegment direction="center-center" />
        <div className="relative z-10 mx-auto w-full max-w-[1120px] overflow-hidden rounded-[2rem] border border-[var(--border-strong)] bg-[var(--accent-strong)] px-6 py-14 text-center text-white shadow-[0_22px_60px_rgba(41,37,36,0.16)] sm:px-12 sm:py-20">
          <WaveMark className="mx-auto w-32 text-white/50" />
          <p className="mt-6 text-sm font-semibold text-white/75">A more connected view of care</p>
          <h2 className="mx-auto mt-5 max-w-[760px] text-3xl font-semibold tracking-[-0.035em] sm:text-5xl">Hold onto the thread without losing the human story.</h2>
          <p className="mx-auto mt-5 max-w-[640px] text-sm leading-6 text-white/80 sm:text-base">
            One client relationship. One continuous record of care and practice activity. A private, clinician-guided workspace for understanding the journey and managing what comes next.
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
