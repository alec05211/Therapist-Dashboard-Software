"use client";

import { useEffect, useState } from "react";
import { LoadingSpinner } from "@/components/loading-spinner";

const fieldDefinitions = [
  ["payer_name", "Insurance company"],
  ["plan_name", "Plan name"],
  ["plan_type", "Plan type"],
  ["member_name", "Member name"],
  ["member_id", "Member ID"],
  ["group_number", "Group number"],
  ["coverage_effective_date", "Effective date"],
  ["member_services_phone", "Member services"],
  ["behavioral_health_phone", "Behavioral health"],
  ["provider_services_phone", "Provider services"],
  ["claims_address", "Claims address"],
  ["rx_bin", "Rx BIN"],
  ["rx_pcn", "Rx PCN"],
  ["rx_group", "Rx group"],
] as const;

type FieldKey = typeof fieldDefinitions[number][0];
type InsuranceCard = {
  id: string;
  status: "processing" | "ready" | "failed";
  fields: Record<FieldKey, string | null>;
  clientReviewed: boolean;
  updatedAt: string;
};

async function responseBody(response: Response) {
  const body = await response.json().catch(() => ({})) as { detail?: string; card?: InsuranceCard | null };
  if (!response.ok) throw new Error(body.detail || "Could not load insurance details.");
  return body;
}

export function TherapistInsuranceSummary({ clientId }: { clientId?: string }) {
  const [card, setCard] = useState<InsuranceCard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!clientId) {
      void Promise.resolve().then(() => { setError("This client workspace is unavailable."); setLoading(false); });
      return;
    }
    let active = true;
    void fetch(`/api/clients/${encodeURIComponent(clientId)}/insurance-card`, { cache: "no-store" })
      .then(responseBody)
      .then(body => { if (active) setCard(body.card ?? null); })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [clientId]);

  if (loading) return <LoadingSpinner label="Loading insurance details…" />;
  if (error) return <p role="alert" className="mt-5 text-sm text-red-700">{error}</p>;
  if (!card) return <div className="mt-6 rounded-xl border border-stone-200 bg-stone-50 p-4 text-left"><h3 className="text-sm font-semibold text-stone-900">No insurance details on file</h3><p className="mt-1 text-sm leading-6 text-stone-600">The client can add an insurance card from their account settings.</p></div>;
  if (card.status !== "ready") return <div className="mt-6 rounded-xl border border-stone-200 bg-stone-50 p-4 text-left"><h3 className="text-sm font-semibold text-stone-900">Insurance details unavailable</h3><p className="mt-1 text-sm leading-6 text-stone-600">The client’s card has not finished processing. Ask them to review or replace it from their account settings.</p></div>;

  return <div className="mt-6 text-left">
    <section className="overflow-hidden rounded-xl border border-stone-200 bg-stone-50">
      <div className="border-b border-stone-200 px-4 py-3">
        <h3 className="text-sm font-semibold text-stone-900">Insurance details</h3>
        <p className="mt-1 text-xs leading-5 text-stone-500">{card.clientReviewed ? "Reviewed or adjusted by the client" : "Extracted from the client’s card and not yet confirmed by the client"}</p>
      </div>
      <dl className="grid gap-x-6 gap-y-4 p-4 sm:grid-cols-2">
        {fieldDefinitions.map(([key, label]) => <div key={key} className="min-w-0"><dt className="text-xs font-semibold text-stone-500">{label}</dt><dd className="mt-1 break-words text-sm text-stone-900">{card.fields[key] || "Not provided"}</dd></div>)}
      </dl>
    </section>
    <p className="mt-3 text-xs leading-5 text-stone-500">For administrative reference only. Eligibility, benefits, network participation, and payment are not verified.</p>
  </div>;
}
