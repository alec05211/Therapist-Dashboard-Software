import { TextLoadingSkeleton } from "@/components/text-loading-skeleton";

function MaterialSkeleton({ title, widths }: { title: string; widths: string[] }) {
  return <section className="overflow-hidden rounded-xl border border-stone-200 bg-stone-100">
    <div className="p-4"><h4 className="text-base font-semibold text-stone-900">{title}</h4></div>
    <div className="border-t border-stone-200 bg-white px-4 py-4">
      <TextLoadingSkeleton label={`Loading ${title.toLowerCase()}`} widths={widths} />
    </div>
  </section>;
}

export function CompletedSessionLoadingSkeleton() {
  return <section className="w-full rounded-2xl border border-stone-200 bg-white p-5 text-left shadow-sm" aria-label="Loading associated materials" aria-busy="true">
    <h3 className="text-base font-semibold text-stone-900">Associated materials</h3>
    <div className="mt-5 grid gap-5">
      <MaterialSkeleton title="Clinical Note" widths={["44%", "91%", "76%"]} />
      <MaterialSkeleton title="Transcript" widths={["82%", "94%", "71%"]} />
    </div>
  </section>;
}

export function ClinicalWorkspaceLoadingSkeleton() {
  return <div className="text-left" aria-label="Loading clinical workspace" aria-busy="true">
    <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
      <h2 className="text-base font-semibold text-stone-900">Session history</h2>
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5" aria-hidden="true">
        {["72%", "84%", "66%", "78%", "62%"].map((width, index) => <div key={index} className="rounded-xl border border-stone-200 bg-stone-50 p-3">
          <span className="text-loading-streak block" style={{ width }} />
          <span className="text-loading-streak mt-3 block" style={{ width: index % 2 ? "58%" : "68%" }} />
        </div>)}
      </div>
    </section>
    <div className="mt-6"><CompletedSessionLoadingSkeleton /></div>
  </div>;
}

export function ClientWorkspaceBootSkeleton() {
  return <main className="mx-auto w-[min(92vw,1080px)] pt-3 pb-8" aria-label="Loading secure client workspace" aria-busy="true">
    <section className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
      <div className="flex items-center gap-4 p-5">
        <span aria-hidden="true" className="size-14 shrink-0 rounded-full bg-stone-200 blur-[1px]" />
        <div className="min-w-0 flex-1">
          <TextLoadingSkeleton label="Loading client identity" widths={["28%", "48%"]} />
        </div>
      </div>
      <nav aria-label="Loading client navigation" className="grid grid-cols-2 border-t border-stone-200 text-center text-sm font-semibold text-stone-600 sm:grid-cols-3 lg:grid-cols-6">
        {["Clinical Workspace", "Insights", "Documents", "Billing", "Chat", "Client Care Settings"].map((label) => <span key={label} className="border-stone-200 px-3 py-3.5 lg:border-l first:lg:border-l-0">{label}</span>)}
      </nav>
    </section>
    <div className="mt-6"><ClinicalWorkspaceLoadingSkeleton /></div>
  </main>;
}
