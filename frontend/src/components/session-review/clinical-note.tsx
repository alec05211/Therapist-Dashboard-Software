import { useState } from "react";
import type { ClinicalNoteSection } from "@/lib/types";

export function ClinicalNote({ sections }: { sections: ClinicalNoteSection[] }) {
  const [expanded, setExpanded] = useState(false);
  if (!sections.length) return null;

  const highlights = sections.flatMap((section) => section.items.map((item) => `${section.name}: ${item}`)).slice(0, 2);
  return (
    <section className="mt-5 overflow-hidden rounded-xl bg-emerald-50" aria-label="HealthScribe clinical note">
      <button
        type="button"
        className="flex w-full items-center justify-between p-4 text-left font-semibold hover:bg-emerald-100 focus-visible:outline-2 focus-visible:outline-emerald-700"
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
      >
        Draft clinical note — review before use <span aria-hidden="true">{expanded ? "⌃" : "⌄"}</span>
      </button>
      {!expanded ? <p className="px-4 pb-4 text-sm text-emerald-950/70">{highlights.join(" · ") || "No note details available."}</p> : null}
      {expanded ? <div className="border-t border-emerald-200 px-4 pb-4">{sections.map((section) => <div key={section.name}><h3 className="mt-4 text-sm font-semibold">{section.name}</h3><ul className="mt-1 list-disc pl-5 text-sm">{section.items.map((item) => <li key={item}>{item}</li>)}</ul></div>)}</div> : null}
    </section>
  );
}
