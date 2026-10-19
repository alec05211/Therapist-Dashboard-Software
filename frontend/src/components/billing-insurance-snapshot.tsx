"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LoadingSpinner } from "@/components/loading-spinner";

const snapshotFields = [
  ["payer_name", "Insurance company"],
  ["plan_name", "Plan"],
  ["member_name", "Member"],
  ["member_id", "Member ID"],
  ["group_number", "Group number"],
  ["behavioral_health_phone", "Behavioral health"],
] as const;

type SnapshotField = typeof snapshotFields[number][0];
type InsuranceCard = {
  id: string;
  status: "processing" | "ready" | "failed";
  fields: Record<SnapshotField, string | null> & { member_services_phone?: string | null };
  source?: "openai" | "client";
  clientReviewed?: boolean;
};

async function responseBody(response: Response) {
  const body = await response.json().catch(() => ({})) as { detail?: string; card?: InsuranceCard | null };
  if (!response.ok) throw new Error(body.detail || "Could not load insurance details.");
  return body;
}

export function BillingInsuranceSnapshot({ role, clientId }: { role: "client" | "therapist"; clientId?: string }) {
  const [card, setCard] = useState<InsuranceCard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (role === "therapist" && !clientId) {
      void Promise.resolve().then(() => { setError("This client workspace is unavailable."); setLoading(false); });
      return;
    }
    let active = true;
    const endpoint = role === "client"
      ? "/api/account/insurance-card"
      : `/api/clients/${encodeURIComponent(clientId!)}/insurance-card`;
    void fetch(endpoint, { cache: "no-store" })
      .then(responseBody)
      .then(body => { if (active) setCard(body.card ?? null); })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [clientId, role]);

  const action = role === "client" ? <Link href="/settings?section=insurance" className="cursor-grab rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700 transition-colors duration-200 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing">{card ? "Manage insurance" : "Add insurance card"}</Link> : null;
  const reviewed = card?.clientReviewed ?? card?.source === "client";

  return <section className="rounded-2xl border border-stone-200 bg-stone-50 text-left shadow-sm">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 px-5 py-4">
      <div><h2 className="text-xl font-semibold text-stone-900">Insurance</h2><p className="mt-1 text-sm text-stone-600">Coverage information on file</p></div>
      {action}
    </div>
    {loading ? <div className="p-5"><LoadingSpinner label="Loading insurance details…" /></div> : error ? <p role="alert" className="p-5 text-sm text-red-700">{error}</p> : !card ? <div className="p-5"><p className="text-sm font-semibold text-stone-900">No insurance details on file</p><p className="mt-1 text-sm leading-6 text-stone-600">{role === "client" ? "Add a card to keep your coverage information available here." : "The client has not added an insurance card."}</p></div> : card.status !== "ready" ? <div className="p-5"><p className="text-sm font-semibold text-stone-900">Insurance details unavailable</p><p className="mt-1 text-sm leading-6 text-stone-600">{role === "client" ? "Review or replace the card from Insurance Settings." : "The client’s card has not finished processing."}</p></div> : <>
      <div className="flex items-center justify-between gap-3 px-5 pt-4"><p className="text-xs text-stone-500">{reviewed ? "Reviewed or adjusted by the client" : "Extracted from the card and not yet confirmed"}</p></div>
      <dl className="grid gap-x-6 gap-y-4 p-5 sm:grid-cols-2 lg:grid-cols-3">
        {snapshotFields.map(([key, label]) => {
          const value = key === "behavioral_health_phone" ? card.fields[key] || card.fields.member_services_phone : card.fields[key];
          return <div key={key} className="min-w-0"><dt className="text-xs font-semibold text-stone-500">{label}</dt><dd className="mt-1 break-words text-sm text-stone-900">{value || "Not provided"}</dd></div>;
        })}
      </dl>
    </>}
    <p className="border-t border-stone-200 px-5 py-3 text-xs leading-5 text-stone-500">Eligibility, benefits, network participation, and payment are not verified.</p>
  </section>;
}
