import { useState } from "react";
import type { ClinicalNoteSection } from "@/lib/types";

export function ClinicalNote({ sections }: { sections: ClinicalNoteSection[] }) {
  const [expanded, setExpanded] = useState(false);
  if (!sections.length) return null;

  const highlights = sections.flatMap((section) => section.items.map((item) => `${section.name}: ${item}`)).slice(0, 2);
  const toggle = () => setExpanded((value) => !value);
  return (
    <section
      className="relative mt-5 cursor-grab overflow-hidden rounded-xl bg-stone-100 text-stone-900 transition hover:bg-stone-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-stone-700 active:cursor-grabbing"
      aria-label="HealthScribe clinical note"
      aria-expanded={expanded}
      role="button"
      tabIndex={0}
      onClick={toggle}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          toggle();
        }
      }}
    >
      <div className="p-4 text-left font-semibold">
        <span>Draft clinical note — review before use</span>
      </div>
      {!expanded ? <p className="px-4 pb-8 text-sm text-stone-600">{highlights.join(" · ") || "No note details available."}</p> : null}
      {expanded ? <div className="px-4 pb-4">{sections.map((section) => <div key={section.name}><h3 className="mt-4 text-sm font-semibold">{section.name}</h3><ul className="mt-1 list-disc pl-5 text-sm">{section.items.map((item) => <li key={item}>{item}</li>)}</ul></div>)}</div> : null}
      <span className={`absolute right-4 text-lg text-stone-600 ${expanded ? "top-3" : "bottom-2"}`} aria-hidden="true">{expanded ? "⌃" : "⌄"}</span>
    </section>
  );
}
