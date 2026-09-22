import type { ReactNode } from "react";

export type SettingsSection = { id: string; title: string };

type Props = {
  title?: string;
  sections: SettingsSection[];
  activeSection: string;
  onSelect: (id: string) => void;
  navigationLabel: string;
  children: ReactNode;
  headingLevel?: "h1" | "h2";
};

export const settingsFieldClass = "mt-1 block w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 focus:outline-none focus-visible:border-stone-500";

export function SettingsLayout({ title, sections, activeSection, onSelect, navigationLabel, children, headingLevel = "h1" }: Props) {
  const Heading = headingLevel;
  const PanelHeading = headingLevel === "h1" ? "h2" : "h3";
  const active = sections.find((section) => section.id === activeSection) ?? sections[0];

  return <div>
    {title ? <Heading className="text-3xl font-semibold tracking-tight text-stone-900">{title}</Heading> : null}
    <div className={`${title ? "mt-8" : ""} grid gap-4 md:grid-cols-[220px_minmax(0,1fr)]`}>
      <nav className="flex gap-1 overflow-x-auto rounded-2xl border border-stone-200 bg-stone-100 p-2 shadow-sm md:block" aria-label={navigationLabel}>
        {sections.map((section) => <button key={section.id} type="button" onClick={() => onSelect(section.id)} className={`w-full cursor-grab rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-colors duration-200 ease-out active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${activeSection === section.id ? "bg-emerald-50 text-emerald-900" : "text-stone-600 hover:bg-stone-100"}`}>{section.title}</button>)}
      </nav>
      <section className="rounded-2xl border border-stone-200 bg-stone-100 p-2 shadow-sm">
        <div className="min-h-full rounded-xl border border-stone-200 bg-white p-6">
          <PanelHeading className="text-lg font-semibold text-stone-900">{active.title}</PanelHeading>
          {children}
        </div>
      </section>
    </div>
  </div>;
}
