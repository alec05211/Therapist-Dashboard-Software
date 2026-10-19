"use client";

import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { LoadingSpinner } from "@/components/loading-spinner";
import { settingsFieldClass } from "@/components/settings-layout";

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
type InsuranceFields = Record<FieldKey, string | null>;
type Card = {
  id: string;
  status: "processing" | "ready" | "failed";
  frontFilename: string;
  backFilename: string;
  fields: InsuranceFields;
  source: "openai" | "client";
  model: string | null;
  analyzedAt: string | null;
  updatedAt: string;
};

const emptyFields = Object.fromEntries(fieldDefinitions.map(([key]) => [key, null])) as InsuranceFields;

async function responseBody(response: Response, fallback: string) {
  const body = await response.json().catch(() => ({})) as { detail?: string; card?: Card | null };
  if (!response.ok) throw new Error(body.detail || fallback);
  return body;
}

export function InsuranceCardSettings() {
  const [card, setCard] = useState<Card | null>(null);
  const [draft, setDraft] = useState<InsuranceFields>(emptyFields);
  const [front, setFront] = useState<File | null>(null);
  const [back, setBack] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void fetch("/api/account/insurance-card", { cache: "no-store" })
      .then(response => responseBody(response, "Could not load insurance information."))
      .then(body => { if (active) { setCard(body.card ?? null); setDraft(body.card?.fields ?? emptyFields); } })
      .catch((reason: Error) => { if (active) setError(reason.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const choose = (side: "front" | "back", event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    if (file && (file.size > 5 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(file.type))) {
      setError("Choose JPEG, PNG, or WebP images no larger than 5 MB each.");
      event.target.value = "";
      return;
    }
    setError(null); setSaved(false);
    if (side === "front") setFront(file); else setBack(file);
  };

  const upload = async (event: FormEvent) => {
    event.preventDefault();
    if (!front || !back || busy) return;
    const formElement = event.currentTarget;
    setBusy(true); setError(null); setSaved(false);
    try {
      const form = new FormData(); form.append("front", front); form.append("back", back);
      const body = await responseBody(await fetch("/api/account/insurance-card", { method: "POST", body: form }), "Could not analyze the insurance card.");
      setCard(body.card ?? null); setDraft(body.card?.fields ?? emptyFields); setFront(null); setBack(null); setEditing(false); setSaved(true);
      const inputs = formElement.querySelectorAll<HTMLInputElement>('input[type="file"]');
      inputs.forEach(input => { input.value = ""; });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not analyze the insurance card.");
      const current = await fetch("/api/account/insurance-card", { cache: "no-store" })
        .then(response => responseBody(response, "Could not refresh insurance information."))
        .catch(() => null);
      if (current) { setCard(current.card ?? null); setDraft(current.card?.fields ?? emptyFields); }
    }
    finally { setBusy(false); }
  };

  const save = async () => {
    if (busy) return;
    setBusy(true); setError(null); setSaved(false);
    try {
      const body = await responseBody(await fetch("/api/account/insurance-card", {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fields: draft }),
      }), "Could not save insurance details.");
      setCard(body.card ?? null); setDraft(body.card?.fields ?? emptyFields); setEditing(false); setSaved(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save insurance details."); }
    finally { setBusy(false); }
  };

  if (loading) return <LoadingSpinner label="Loading insurance information…" />;

  return <div className="mt-6 space-y-6">
    <section className="rounded-xl border border-stone-200 bg-stone-50 p-4">
      <h3 className="text-sm font-semibold text-stone-900">Insurance card</h3>
      <p className="mt-1 text-sm leading-6 text-stone-600">Upload clear images of both sides. AI extracts visible administrative details only; it does not verify eligibility, benefits, network participation, or payment.</p>
      <form onSubmit={upload} className="mt-4 space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          {(["front", "back"] as const).map(side => {
            const file = side === "front" ? front : back;
            const storedName = side === "front" ? card?.frontFilename : card?.backFilename;
            return <label key={side} className={`block rounded-xl border border-dashed border-stone-300 bg-white p-4 ${busy ? "cursor-wait opacity-70" : "cursor-grab active:cursor-grabbing"}`}>
              <span className="block text-sm font-semibold capitalize text-stone-800">{side} of card</span>
              <span className="mt-1 block truncate text-xs text-stone-500">{file?.name ?? storedName ?? "Choose an image"}</span>
              <input type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={event => choose(side, event)} className="sr-only" />
            </label>;
          })}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" disabled={!front || !back || busy} className="cursor-grab rounded-lg bg-emerald-800 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-900 disabled:cursor-not-allowed disabled:opacity-60 active:cursor-grabbing">{busy ? "Securing and analyzing…" : card ? "Replace and analyze card" : "Upload and analyze card"}</button>
          <span className="text-xs text-stone-500">JPEG, PNG, or WebP · up to 5 MB per side</span>
        </div>
      </form>
    </section>

    {card?.status === "failed" && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">The images were stored securely, but analysis did not finish. Choose both images and upload again to retry.</p>}

    {card?.status === "ready" && <section className="rounded-xl border border-stone-200 bg-stone-50">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 px-4 py-3">
        <div><h3 className="text-sm font-semibold text-stone-900">Insurance details</h3><p className="mt-1 text-xs text-stone-500">{card.source === "client" ? "Adjusted by you" : "Extracted from your card—review for accuracy"}</p></div>
        {!editing ? <button type="button" onClick={() => { setDraft(card.fields); setEditing(true); setSaved(false); }} className="cursor-grab rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-100 active:cursor-grabbing">Edit</button> : <div className="flex gap-2"><button type="button" onClick={() => void save()} disabled={busy} className="cursor-grab rounded-lg bg-emerald-800 px-3 py-2 text-sm font-semibold text-white disabled:cursor-wait active:cursor-grabbing">{busy ? "Saving…" : "Save"}</button><button type="button" onClick={() => { setDraft(card.fields); setEditing(false); setError(null); }} disabled={busy} className="cursor-grab rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700 disabled:cursor-not-allowed active:cursor-grabbing">Cancel</button></div>}
      </div>
      <div className="grid gap-4 p-4 sm:grid-cols-2">
        {fieldDefinitions.map(([key, label]) => <label key={key} className="block text-sm font-semibold text-stone-800">{label}<input readOnly={!editing} maxLength={500} value={draft[key] ?? ""} placeholder={editing ? "Not shown on card" : "Not found"} onChange={event => setDraft(current => ({ ...current, [key]: event.target.value || null }))} className={`${settingsFieldClass} ${editing ? "" : "cursor-default bg-stone-100 text-stone-700"}`} /></label>)}
      </div>
    </section>}

    {saved && <p role="status" className="text-sm font-medium text-emerald-800">Insurance information saved.</p>}
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
  </div>;
}
