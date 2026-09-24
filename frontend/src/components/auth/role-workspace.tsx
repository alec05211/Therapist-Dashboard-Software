"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LoadingSpinner } from "@/components/loading-spinner";
import { ClientPortal } from "@/components/client-portal";
import { SessionWorkspace } from "@/components/session-review/session-workspace";

import type { CareProfile } from "@/components/care-relationship-header";

type Identity = { role: "therapist" | "client"; displayName: string; profile: CareProfile };

export function RoleWorkspace({ clientId, initialClientView = "clinical-workspace" }: {
  clientId?: string;
  initialClientView?: "clinical-workspace" | "chat";
}) {
  const router = useRouter();
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/identity/me", { cache: "no-store", signal: controller.signal }).then(async response => {
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Your account is not connected to this workspace.");
      if (body.role === "therapist" && !clientId) { router.replace("/clients"); return; }
      if (body.role !== "therapist" && clientId) throw new Error("This client workspace is available to therapists only.");
      const profileResponse = await fetch(`/api/relationship-profile${clientId ? `?client_id=${encodeURIComponent(clientId)}` : ""}`, { cache: "no-store", signal: controller.signal });
      const profile = await profileResponse.json();
      if (!profileResponse.ok) throw new Error(profile.detail || "Could not load the care profile.");
      if (!controller.signal.aborted) setIdentity({ ...body, profile });
    }).catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Could not load your account."); });
    return () => controller.abort();
  }, [clientId, router]);
  if (error) return <main className="mx-auto w-[min(92vw,680px)] py-12"><section className="rounded-2xl border border-stone-200 bg-white p-7 shadow-sm"><h1 className="text-xl font-semibold text-stone-900">Workspace unavailable</h1><p className="mt-3 text-sm leading-6 text-stone-600">{error}</p>{clientId && <Link href="/clients" className="mt-4 inline-block cursor-grab text-sm font-semibold text-emerald-800 active:cursor-grabbing">Back to client list</Link>}</section></main>;
  if (!identity) return <main className="mx-auto w-[min(92vw,680px)] py-12 text-sm text-stone-600"><LoadingSpinner label="Loading your secure workspace…" /></main>;
  return identity.role === "client" ? <ClientPortal name={identity.displayName} profile={identity.profile} /> : <SessionWorkspace profile={identity.profile} initialView={initialClientView} />;
}
