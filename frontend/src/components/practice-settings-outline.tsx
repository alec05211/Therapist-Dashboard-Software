"use client";

import { useState, type ReactNode } from "react";
import { SettingsLayout, type SettingsSection } from "@/components/settings-layout";

type PracticeSection = SettingsSection & {
  introduction: string;
  groups: Array<{ title: string; description: string; items: string[]; note?: ReactNode }>;
};

const sections: PracticeSection[] = [
  { id: "overview", title: "Overview", introduction: "The essentials for operating a solo practice today and adding a team later.", groups: [
    { title: "Practice workspace", description: "One organization contains the operational settings for this practice.", items: ["Practice profile and public presence", "Services, locations, and appointment types", "Team roles and client-specific access"] },
    { title: "Setup path", description: "A suggested order for turning this outline into a working practice.", items: ["Complete practice identity", "Define services and availability", "Configure intake and consent", "Connect billing and review security"] },
  ] },
  { id: "identity", title: "Practice identity", introduction: "How the practice appears to clients, staff, and in generated documents.", groups: [
    { title: "Profile", description: "Core business and contact information.", items: ["Practice name and logo", "Phone, email, website, and timezone", "Business address and service locations"] },
    { title: "Public presence", description: "Information used for future discovery and intake.", items: ["Practice description and specialties", "Populations served and languages", "New-client availability and referral preferences"] },
  ] },
  { id: "services", title: "Services & locations", introduction: "Define what the practice offers and where care can take place.", groups: [
    { title: "Services", description: "Reusable defaults for scheduling and billing.", items: ["Individual, couples, family, and group offerings", "Default duration and fee", "In-person, phone, or telehealth delivery"] },
    { title: "Locations", description: "Places associated with appointments.", items: ["Office locations and accessibility details", "Telehealth availability by jurisdiction", "Location-specific hours and instructions"] },
  ] },
  { id: "team", title: "Team & access", introduction: "Keep operational authority separate from access to clinical records.", groups: [
    { title: "Practice roles", description: "A member may hold more than one role.", items: ["Owner and administrator", "Therapist, associate or intern, and supervisor", "Scheduler and billing staff"] },
    { title: "Clinical access", description: "Practice membership alone never opens a client record.", items: ["Primary or collaborating therapist assignment", "Explicit supervision relationship", "Time-limited coverage and access revocation"], note: <p className="mt-4 rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-sm leading-6 text-emerald-900">Administrators manage the practice environment. They receive clinical access only when they are also an authorized practitioner on that client’s care team.</p> },
  ] },
  { id: "scheduling", title: "Scheduling", introduction: "Practice-wide scheduling rules with personal availability owned by each therapist.", groups: [
    { title: "Appointment defaults", description: "Shared choices for consistent scheduling.", items: ["Appointment types and durations", "Cancellation and no-show policies", "Reminder timing and delivery channels"] },
    { title: "Availability", description: "Working hours and calendar behavior.", items: ["Regular availability and blocked time", "Minimum notice and booking horizon", "Calendar integration and conflict handling"] },
  ] },
  { id: "intake", title: "Intake & consent", introduction: "Guide a prospective client into an appropriately consented care relationship.", groups: [
    { title: "Intake flow", description: "Define the path from inquiry to active client.", items: ["Inquiry and consultation stages", "Intake forms and required documents", "Therapist matching and acceptance"] },
    { title: "Consent", description: "Make sensitive-data expectations explicit.", items: ["Practice and privacy acknowledgements", "Recording and transcription consent", "Client portal and information-sharing choices"] },
  ] },
  { id: "billing", title: "Billing & insurance", introduction: "A future home for the financial defaults of the practice.", groups: [
    { title: "Rates and payments", description: "Defaults that can be adjusted for an individual care relationship.", items: ["Service rates and sliding-scale arrangements", "Invoices, statements, receipts, and balances", "Payment processor and payout configuration"] },
    { title: "Insurance", description: "Operational support without exposing clinical material unnecessarily.", items: ["Payer and credentialing information", "Service and diagnosis-code workflows", "Claims, remittance, and client responsibility"] },
  ] },
  { id: "clinical", title: "Clinical workflow", introduction: "Organization defaults that support, but never replace, clinician judgment.", groups: [
    { title: "Session records", description: "Defaults for creating and reviewing sensitive session material.", items: ["Recording and transcription defaults", "Draft clinical-note templates", "Finalization and amendment workflow"] },
    { title: "Client sharing", description: "Therapists retain control of client-facing clinical materials.", items: ["Transcript and recording playback", "Clinical Note and Insights visibility", "Permission dependencies and revocation"] },
  ] },
  { id: "security", title: "Data & security", introduction: "Organization-wide safeguards and accountable administrative actions.", groups: [
    { title: "Data governance", description: "Policies to define before use with real therapy sessions.", items: ["Retention, deletion, and legal-hold expectations", "Export and practice-transition procedures", "Vendor and data-processing boundaries"] },
    { title: "Security", description: "Controls reserved for owners and authorized administrators.", items: ["Authentication and active-session policy", "Audit history and permission changes", "Integrations, ownership transfer, and practice closure"] },
  ] },
];

export function PracticeSettingsOutline() {
  const [activeSection, setActiveSection] = useState("overview");
  const active = sections.find(section => section.id === activeSection) ?? sections[0];

  return <main className="mx-auto w-[min(94vw,1120px)] py-10">
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-sm font-semibold text-emerald-800">Solo practice workspace</p><h1 className="mt-1 text-3xl font-semibold tracking-tight text-stone-900">Practice</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-stone-600">A launch pad for the operational controls that belong to the practice rather than one client relationship.</p></div>
      <div className="rounded-xl border border-stone-300 bg-white px-4 py-3 text-right shadow-sm"><p className="text-xs font-medium uppercase tracking-[0.12em] text-stone-500">Your access</p><p className="mt-1 text-sm font-semibold text-stone-900">Owner · Therapist</p></div>
    </div>

    <SettingsLayout sections={sections} activeSection={active.id} onSelect={setActiveSection} navigationLabel="Practice setting sections" headingLevel="h2">
      <p className="mt-2 text-sm leading-6 text-stone-600">{active.introduction}</p>
      <div className="mt-6 space-y-4">
        {active.groups.map(group => <section key={group.title} className="rounded-xl border border-stone-300 bg-stone-50 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold text-stone-900">{group.title}</h3><p className="mt-1 text-sm leading-6 text-stone-600">{group.description}</p></div><span className="rounded-full border border-stone-300 bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-stone-600">Outline</span></div>
          <ul className="mt-4 divide-y divide-stone-200 border-y border-stone-200">
            {group.items.map(item => <li key={item} className="flex items-center gap-3 py-3 text-sm text-stone-800"><span aria-hidden="true" className="size-1.5 shrink-0 rounded-full bg-emerald-800" />{item}</li>)}
          </ul>
          {group.note}
        </section>)}
      </div>
      <p className="mt-6 text-xs leading-5 text-stone-500">Concept interface only. These controls are not connected to persisted practice settings yet.</p>
    </SettingsLayout>
  </main>;
}
