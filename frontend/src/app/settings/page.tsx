"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";

const sections = [
  ["Profile", "Name, professional details, and contact information"],
  ["Security", "Password, sign-in methods, and active sessions"],
  ["Notifications", "Appointment and workflow notification preferences"],
  ["Appearance", "Choose the workspace color theme"],
];

type Theme = "light" | "dark";
const themeChanged = "therapist-dashboard-theme-changed";

function subscribeToTheme(onStoreChange: () => void) {
  window.addEventListener(themeChanged, onStoreChange);
  return () => window.removeEventListener(themeChanged, onStoreChange);
}

function readTheme(): Theme {
  return window.localStorage.getItem("therapist-dashboard-theme") === "dark" ? "dark" : "light";
}

function chooseTheme(theme: Theme) {
  window.localStorage.setItem("therapist-dashboard-theme", theme);
  window.dispatchEvent(new Event(themeChanged));
}

export default function AccountSettingsPage() {
  const [active, setActive] = useState("Profile");
  const theme = useSyncExternalStore(subscribeToTheme, readTheme, () => "light");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

  return (
    <main className="mx-auto w-[min(94vw,960px)] py-10">
      <p className="text-sm font-medium text-emerald-800">Account</p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight text-stone-900">Account settings</h1>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-stone-600">Manage settings that belong to you, regardless of which client or session you are working with.</p>
      <div className="mt-8 grid gap-6 md:grid-cols-[220px_minmax(0,1fr)]">
        <nav className="flex gap-1 overflow-x-auto md:block" aria-label="Account setting sections">
          {sections.map(([title, description]) => <button key={title} type="button" onClick={() => setActive(title)} className={`w-full rounded-lg px-3 py-2.5 text-left text-sm font-medium ${active === title ? "bg-emerald-50 text-emerald-900" : "text-stone-600 hover:bg-stone-100"}`}><span className="block">{title}</span><span className="mt-0.5 hidden text-xs font-normal leading-4 text-stone-500 md:block">{description}</span></button>)}
        </nav>
        <section className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-stone-900">{active}</h2>
          <p className="mt-2 text-sm leading-6 text-stone-600">{sections.find(([title]) => title === active)?.[1]}</p>
          {active === "Appearance" ? <div className="mt-6 grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Color theme">
            {(["light", "dark"] as Theme[]).map((option) => <button key={option} type="button" role="radio" aria-checked={theme === option} onClick={() => chooseTheme(option)} className={`rounded-xl border p-4 text-left transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${theme === option ? "border-emerald-700 bg-emerald-50 ring-1 ring-emerald-700" : "border-stone-300 hover:bg-stone-50"}`}>
              <span className={`mb-4 block h-20 rounded-lg border p-3 ${option === "light" ? "border-stone-200 bg-white" : "border-stone-700 bg-stone-900"}`} aria-hidden="true"><span className={`block h-2 w-16 rounded ${option === "light" ? "bg-stone-300" : "bg-stone-600"}`} /><span className={`mt-2 block h-6 rounded ${option === "light" ? "bg-stone-100" : "bg-stone-800"}`} /></span>
              <span className="block text-sm font-semibold capitalize text-stone-900">{option}</span><span className="mt-1 block text-xs text-stone-500">{option === "light" ? "Bright, calm workspace" : "Lower-light workspace"}</span>
            </button>)}
          </div> : <><div className="mt-6 rounded-xl bg-stone-50 p-4 text-sm text-stone-600">This is the initial account-settings destination. Profile fields and authentication are still managed through the existing account and onboarding flows.</div><Link href="/onboarding/therapist" className="mt-5 inline-flex rounded-lg border border-stone-300 px-3.5 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50">Open therapist profile</Link></>}
        </section>
      </div>
    </main>
  );
}
