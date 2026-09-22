"use client";

import Image from "next/image";
import type { ReactNode } from "react";

export type CareProfile = {
  name: string;
  role: "Client" | "Therapist";
  initials: string;
  email?: string | null;
  phone?: string | null;
  imageSrc?: string;
  aboutMe?: string | null;
  organizationId?: string | null;
  clientId?: string | null;
  syntheticCase?: boolean;
};

export type CareAction = {
  id: string;
  label: string;
  icon: "workspace" | "billing" | "documents" | "insights" | "settings" | "chat" | "prescriptions";
  onSelect?: () => void;
  comingSoon?: boolean;
};

function MailIcon() {
  return <svg aria-hidden="true" className="size-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="m3.75 6.75 7.5 5.25a1.3 1.3 0 0 0 1.5 0l7.5-5.25M5.25 4.5h13.5c.83 0 1.5.67 1.5 1.5v12c0 .83-.67 1.5-1.5 1.5H5.25c-.83 0-1.5-.67-1.5-1.5V6c0-.83.67-1.5 1.5-1.5Z" /></svg>;
}

function PhoneIcon() {
  return <svg aria-hidden="true" className="size-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M6.62 3.75h2.2c.5 0 .94.33 1.08.8l.88 3.07a1.13 1.13 0 0 1-.52 1.29L8.7 9.8a12.04 12.04 0 0 0 5.5 5.5l.9-1.55a1.13 1.13 0 0 1 1.29-.52l3.07.88c.47.14.8.58.8 1.08v2.2c0 .62-.5 1.13-1.13 1.13C10.55 18.52 5.48 13.45 5.48 4.88c0-.62.5-1.13 1.13-1.13Z" /></svg>;
}

function ChatIcon() {
  return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M7.5 18.75 3.75 20.25l1.5-3.75a7.5 7.5 0 1 1 2.25 2.25Z" /><path strokeLinecap="round" d="M8.25 12h.01m3.74 0H12m3.74 0h.01" /></svg>;
}

function WorkspaceIcon() {
  return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 5.25c0-.83.67-1.5 1.5-1.5h12c.83 0 1.5.67 1.5 1.5v13.5c0 .83-.67 1.5-1.5 1.5H6c-.83 0-1.5-.67-1.5-1.5V5.25ZM8.25 8.25h7.5m-7.5 3h7.5m-7.5 3h4.5" /></svg>;
}

function BillingIcon() {
  return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3.75h10.5c.83 0 1.5.67 1.5 1.5v13.5c0 .83-.67 1.5-1.5 1.5H6.75c-.83 0-1.5-.67-1.5-1.5V5.25c0-.83.67-1.5 1.5-1.5ZM8.25 8.25h7.5m-7.5 3h7.5m-7.5 3h3" /></svg>;
}

function DocumentsIcon() {
  return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3.75h7.5l3 3v13.5H6.75V3.75Z" /><path strokeLinecap="round" strokeLinejoin="round" d="M14.25 3.75v3h3M9 11.25h6m-6 3h6m-6 3h3.75" /></svg>;
}

function InsightsIcon() {
  return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5V10.88c0-.62.5-1.13 1.13-1.13h1.74c.62 0 1.13.5 1.13 1.13v8.62m0 0h3V5.63c0-.62.5-1.13 1.13-1.13h1.74c.62 0 1.13.5 1.13 1.13V19.5m0 0h3v-5.62c0-.62.5-1.13 1.13-1.13h.24c.62 0 1.13.5 1.13 1.13v5.62M3 19.5h18" /><path strokeLinecap="round" strokeLinejoin="round" d="m8.25 13.5 2.25-2.25 1.5 1.5 3.75-3.75" /></svg>;
}

function CareSettingsIcon() {
  return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M10.3 4.32a1.65 1.65 0 0 1 3.4 0l.16.9a1.65 1.65 0 0 0 2.48 1.17l.78-.47a1.65 1.65 0 0 1 2.4 2.4l-.47.78a1.65 1.65 0 0 0 1.17 2.48l.9.16a1.65 1.65 0 0 1 0 3.4l-.9.16a1.65 1.65 0 0 0-1.17 2.48l.47.78a1.65 1.65 0 0 1-2.4 2.4l-.78-.47a1.65 1.65 0 0 0-2.48 1.17l-.16.9a1.65 1.65 0 0 1-3.4 0l-.16-.9a1.65 1.65 0 0 0-2.48-1.17l-.78.47a1.65 1.65 0 0 1-2.4-2.4l.47-.78a1.65 1.65 0 0 0-1.17-2.48l-.9-.16a1.65 1.65 0 0 1 0-3.4l.9-.16A1.65 1.65 0 0 0 5.2 8.66l-.47-.78a1.65 1.65 0 0 1 2.4-2.4l.78.47a1.65 1.65 0 0 0 2.48-1.17l.16-.9Z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></svg>;
}


function PrescriptionIcon() {
  return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="m9 15 6-6M6 18a4.24 4.24 0 0 1 0-6l6-6a4.24 4.24 0 0 1 6 6l-6 6a4.24 4.24 0 0 1-6 0ZM9 9l6 6" /></svg>;
}

const icons: Record<CareAction["icon"], ReactNode> = {
  workspace: <WorkspaceIcon />, billing: <BillingIcon />, documents: <DocumentsIcon />,
  insights: <InsightsIcon />, settings: <CareSettingsIcon />, chat: <ChatIcon />,
  prescriptions: <PrescriptionIcon />,
};

export function CareRelationshipHeader({ profile, actions, activeAction }: {
  profile: CareProfile;
  actions: CareAction[];
  activeAction: string;
}) {
  return <section className="mb-6 overflow-hidden rounded-2xl border border-stone-200 bg-stone-50 text-left shadow-sm" aria-label={`${profile.role} details and navigation`}>
    <div className="flex min-w-0 items-center gap-4 p-5">
      <div className="relative grid size-14 shrink-0 place-items-center overflow-hidden rounded-full bg-emerald-800 text-lg font-semibold text-white">
        {profile.imageSrc ? <Image src={profile.imageSrc} alt={`${profile.name} profile`} fill sizes="56px" unoptimized className="object-cover" /> : <span aria-hidden="true">{profile.initials}</span>}
      </div>
      <div className="min-w-0">
        <p className="text-sm font-medium text-emerald-800">{profile.role}</p>
        <h1 className="mt-0.5 break-words text-xl font-semibold tracking-tight text-stone-900">{profile.name}</h1>
        {(profile.email || profile.phone) && <div className="mt-2 flex flex-col gap-1 text-sm text-stone-600 sm:flex-row sm:flex-wrap sm:gap-x-4">
          {profile.email && <a href={`mailto:${profile.email}`} className="inline-flex min-w-0 cursor-grab items-center gap-1.5 rounded hover:text-emerald-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing"><MailIcon /><span className="break-all">{profile.email}</span></a>}
          {profile.phone && <a href={`tel:${profile.phone.replace(/[^+\d]/g, "")}`} className="inline-flex cursor-grab items-center gap-1.5 rounded hover:text-emerald-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing"><PhoneIcon />{profile.phone}</a>}
        </div>}
        {profile.role === "Therapist" && profile.aboutMe && <p className="mt-3 max-w-2xl whitespace-pre-wrap text-sm leading-6 text-stone-600">{profile.aboutMe}</p>}
      </div>
    </div>
    <nav className="flex gap-1 overflow-x-auto border-t border-stone-200 bg-white px-3 py-2" aria-label={`${profile.name} care navigation`}>
      {actions.map(action => <button key={action.id} type="button" disabled={action.comingSoon} onClick={action.onSelect}
        title={action.comingSoon ? `${action.label} is coming soon` : undefined}
        aria-current={activeAction === action.id ? "page" : undefined}
        className={`inline-flex min-w-fit flex-1 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm transition-colors duration-200 ease-out motion-reduce:transition-none ${action.comingSoon ? "cursor-not-allowed font-medium text-stone-500" : `cursor-grab font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing ${activeAction === action.id ? "bg-emerald-50 text-emerald-900" : "text-stone-600 hover:bg-stone-100"}`}`}>
        {icons[action.icon]}{action.label}{action.comingSoon && <span className="rounded-full bg-stone-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-stone-500">Soon</span>}
      </button>)}
    </nav>
  </section>;
}
