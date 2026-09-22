"use client";

import { Suspense, useEffect, useState, useSyncExternalStore } from "react";
import { AccountProfileForm } from "@/components/account-profile-form";
import { SettingsLayout, type SettingsSection } from "@/components/settings-layout";
import { canUseFeature, type AccountRole } from "@/lib/role-capabilities";
import { useRouter, useSearchParams } from "next/navigation";
import { chooseSessionView, readSessionView, subscribeToSessionView, type SessionView } from "@/lib/workspace-preferences";

const sections: SettingsSection[] = [
  { id: "profile", title: "Profile" },
  { id: "security", title: "Security" },
  { id: "notifications", title: "Notifications" },
  { id: "appearance", title: "Appearance" },
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

function AccountSettingsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [role, setRole] = useState<AccountRole | null>(null);
  useEffect(() => { void fetch("/api/identity/me", { cache: "no-store" }).then(response => response.json()).then(body => { if (body.role === "client" || body.role === "therapist") setRole(body.role); }); }, []);
  const active = sections.some((section) => section.id === searchParams.get("section")) ? searchParams.get("section")! : "profile";
  const theme = useSyncExternalStore(subscribeToTheme, readTheme, () => "light");
  const sessionView = useSyncExternalStore(subscribeToSessionView, readSessionView, () => "cards");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

  return (
    <main className="mx-auto w-[min(94vw,960px)] py-10">
      <SettingsLayout title="Account settings" sections={sections} activeSection={active} onSelect={(id) => router.push(`/settings?section=${id}`)} navigationLabel="Account setting sections">
          {active === "appearance" ? <><div className="mt-6 grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Color theme">
            {(["light", "dark"] as Theme[]).map((option) => <button key={option} type="button" role="radio" aria-checked={theme === option} onClick={() => chooseTheme(option)} className={`rounded-xl border p-4 text-left transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${theme === option ? "border-emerald-700 bg-emerald-50 ring-1 ring-emerald-700" : "border-stone-300 hover:bg-stone-50"}`}>
              <span className={`mb-4 block h-20 rounded-lg border p-3 ${option === "light" ? "border-stone-200 bg-white" : "border-stone-700 bg-stone-900"}`} aria-hidden="true"><span className={`block h-2 w-16 rounded ${option === "light" ? "bg-stone-300" : "bg-stone-600"}`} /><span className={`mt-2 block h-6 rounded ${option === "light" ? "bg-stone-100" : "bg-stone-800"}`} /></span>
              <span className="block text-sm font-semibold capitalize text-stone-900">{option}</span><span className="mt-1 block text-xs text-stone-500">{option === "light" ? "Bright, calm workspace" : "Lower-light workspace"}</span>
            </button>)}
          </div>{role && canUseFeature(role, "sessionNavigation") && <div className="mt-8 border-t border-stone-200 pt-6"><h3 className="text-sm font-semibold text-stone-900">Session navigation</h3><p className="mt-1 text-sm leading-6 text-stone-600">Choose how saved sessions are browsed in the client workspace.</p><div className="mt-3 grid gap-3 sm:grid-cols-2" role="radiogroup" aria-label="Session navigation layout">
            {(["cards", "legacy"] as SessionView[]).map((option) => <button key={option} type="button" role="radio" aria-checked={sessionView === option} onClick={() => chooseSessionView(option)} className={`rounded-xl border p-4 text-left transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${sessionView === option ? "border-emerald-700 bg-emerald-50 ring-1 ring-emerald-700" : "border-stone-300 hover:bg-stone-50"}`}><span className="block text-sm font-semibold text-stone-900">{option === "cards" ? "Session cards" : "Legacy list"}</span><span className="mt-1 block text-xs leading-5 text-stone-500">{option === "cards" ? "Five-session carousel with the selected session centered." : "The original vertical list of saved transcripts."}</span></button>)}
          </div></div>}</> : active === "profile" ? <AccountProfileForm /> : <div className="mt-6 rounded-xl border border-stone-200 bg-stone-50 p-4 text-sm text-stone-600">This setting is coming soon.</div>}
      </SettingsLayout>
    </main>
  );
}

export default function AccountSettingsPage() {
  return <Suspense fallback={<main className="mx-auto w-[min(94vw,960px)] py-10" />}><AccountSettingsContent /></Suspense>;
}
