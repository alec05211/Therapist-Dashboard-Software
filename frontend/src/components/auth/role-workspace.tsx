"use client";

import { useEffect, useState } from "react";
import { LoadingSpinner } from "@/components/loading-spinner";
import { ClientPortal } from "@/components/client-portal";
import { SessionWorkspace } from "@/components/session-review/session-workspace";

import type { CareProfile } from "@/components/care-relationship-header";

type Identity = { role: "therapist" | "client"; displayName: string; profile: CareProfile };

export function RoleWorkspace() {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { void fetch("/api/identity/me").then(async (response) => { const body = await response.json(); if (!response.ok) throw new Error(body.detail || "Your account is not connected to this workspace."); const profileResponse = await fetch("/api/relationship-profile", { cache: "no-store" }); const profile = await profileResponse.json(); if (!profileResponse.ok) throw new Error(profile.detail || "Could not load the care profile."); setIdentity({ ...body, profile }); }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Could not load your account.")); }, []);
  if (error) return <main className="mx-auto w-[min(92vw,680px)] py-12"><section className="rounded-2xl border border-stone-200 bg-white p-7 shadow-sm"><h1 className="text-xl font-semibold text-stone-900">Account setup is incomplete</h1><p className="mt-3 text-sm leading-6 text-stone-600">{error}</p></section></main>;
  if (!identity) return <main className="mx-auto w-[min(92vw,680px)] py-12 text-sm text-stone-600"><LoadingSpinner label="Loading your secure workspace…" /></main>;
  return identity.role === "client" ? <ClientPortal name={identity.displayName} profile={identity.profile} /> : <SessionWorkspace profile={identity.profile} />;
}
