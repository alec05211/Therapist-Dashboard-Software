"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LoadingSpinner } from "@/components/loading-spinner";

type Invitation = { id: string; status: "pending" | "accepted" | "declined" | "cancelled"; created_at: string; counterpart_name: string; counterpart_email: string | null; organization_name: string };
type Inbox = { role: "therapist" | "client" | "client_pending" | "unregistered"; unreadCount: number; invitations: Invitation[] };

export default function InboxPage() {
  const router = useRouter();
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const load = useCallback(async () => {
    const response = await fetch("/api/inbox", { cache: "no-store" });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "Could not load your inbox.");
    setInbox(body); window.dispatchEvent(new Event("inbox-changed"));
  }, []);
  useEffect(() => { void Promise.resolve().then(load).catch(reason => setError(reason instanceof Error ? reason.message : "Could not load your inbox.")); }, [load]);
  const respond = async (id: string, action: "accept" | "decline") => {
    setBusyId(id); setError(null);
    try {
      const response = await fetch(`/api/inbox/invitations/${encodeURIComponent(id)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action }) });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || `Could not ${action} this invitation.`);
      await load();
      if (action === "accept") router.push("/");
    } catch (reason) { setError(reason instanceof Error ? reason.message : `Could not ${action} this invitation.`); }
    finally { setBusyId(null); }
  };
  return <main className="mx-auto w-[min(92vw,820px)] py-10 sm:py-12">
    <div className="mb-6"><h1 className="text-2xl font-semibold tracking-tight text-stone-900">Inbox</h1><p className="mt-2 text-sm text-stone-600">Connection invitations and account updates appear here.</p></div>
    <section className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm" aria-busy={!inbox && !error}>
      {!inbox && !error ? <div className="p-8"><LoadingSpinner label="Loading your inbox…" /></div> : error && !inbox ? <p role="alert" className="p-6 text-sm text-red-700">{error}</p> : inbox?.invitations.length ? <ul className="divide-y divide-stone-200">{inbox.invitations.map(invitation => <li key={invitation.id} className="p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="font-semibold text-stone-900">{inbox.role === "therapist" ? invitation.counterpart_name : `${invitation.counterpart_name} invited you to connect`}</p><p className="mt-1 text-sm text-stone-600">{invitation.organization_name}{invitation.counterpart_email ? ` · ${invitation.counterpart_email}` : ""}</p><p className="mt-2 text-xs text-stone-500">{new Date(invitation.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</p></div><span className="rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-xs font-semibold capitalize text-stone-700">{invitation.status}</span></div>
        {(inbox.role === "client_pending" || inbox.role === "client") && invitation.status === "pending" && <div className="mt-5 flex gap-2"><button disabled={busyId === invitation.id} onClick={() => void respond(invitation.id, "accept")} className="cursor-grab rounded-lg bg-emerald-800 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-900 disabled:cursor-wait active:cursor-grabbing">Accept</button><button disabled={busyId === invitation.id} onClick={() => void respond(invitation.id, "decline")} className="cursor-grab rounded-lg border border-stone-300 px-4 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50 disabled:cursor-wait active:cursor-grabbing">Decline</button></div>}
      </li>)}</ul> : <div className="p-8"><h2 className="font-semibold text-stone-900">Your inbox is clear</h2><p className="mt-2 text-sm leading-6 text-stone-600">New invitations and connection updates will appear here.</p></div>}
      {error && inbox && <p role="alert" className="border-t border-stone-200 p-4 text-sm text-red-700">{error}</p>}
    </section>
  </main>;
}
