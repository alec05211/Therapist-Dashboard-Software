import { CollapsibleContentPanel } from "@/components/collapsible-content-panel";
import type { ClinicalNoteSection } from "@/lib/types";

export function ClinicalNote({ sections }: { sections: ClinicalNoteSection[] }) {
  if (!sections.length) return null;
  const preview = sections.flatMap(section => section.items.map(item => `${section.name}: ${item}`)).join(" · ");
  return <CollapsibleContentPanel title="Draft clinical note — review before use" ariaLabel="HealthScribe clinical note" preview={preview || "No note details available."} className="mt-5">
    <div className="px-4 pb-4">{sections.map(section => <div key={section.name}><h3 className="mt-4 text-sm font-semibold">{section.name}</h3><ul className="mt-1 list-disc pl-5 text-sm leading-6">{section.items.map(item => <li key={item}>{item}</li>)}</ul></div>)}</div>
  </CollapsibleContentPanel>;
}
