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
    <div className={`${title ? "mt-8" : ""} grid items-start gap-3 rounded-2xl border border-stone-300 bg-[var(--surface-inset)] p-3 md:grid-cols-[208px_minmax(0,1fr)] md:gap-4 md:p-4`}>
      <nav className="flex min-w-0 gap-1 overflow-x-auto p-1 md:block md:space-y-1" aria-label={navigationLabel}>
        {sections.map((section) => <button key={section.id} type="button" aria-current={activeSection === section.id ? "page" : undefined} onClick={() => onSelect(section.id)} className={`shrink-0 cursor-grab rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-colors duration-200 ease-out active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 md:w-full ${activeSection === section.id ? "bg-emerald-50 text-emerald-900" : "text-stone-600 hover:bg-[var(--surface)]"}`}>{section.title}</button>)}
      </nav>
      <section className="min-w-0 rounded-xl border border-stone-300 bg-white p-4 shadow-sm sm:p-6">
        <PanelHeading className="text-lg font-semibold text-stone-900">{active.title}</PanelHeading>
        {children}
      </section>
    </div>
  </div>;
}
