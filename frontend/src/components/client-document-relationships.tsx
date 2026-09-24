"use client";

import { useEffect, useState } from "react";
import { ClientDocuments } from "@/components/client-documents";
import { LoadingSpinner } from "@/components/loading-spinner";

type Relationship = { organizationId: string; clientId: string; practitionerId: string; therapistName: string };

export function ClientDocumentRelationships() {
  const [relationships, setRelationships] = useState<Relationship[] | null>(null);
  const [selected, setSelected] = useState(0);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/document-relationships", { cache: "no-store", signal: controller.signal }).then(async response => {
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Could not load document spaces.");
      setRelationships(body.relationships);
    }).catch(reason => { if (!controller.signal.aborted) setError(reason.message); });
    return () => controller.abort();
  }, []);
  if (error) return <p role="alert" className="text-sm text-red-700">{error}</p>;
  if (!relationships) return <LoadingSpinner label="Loading document spaces…" />;
  if (!relationships.length) return <p className="text-sm text-stone-600">No active document spaces are available.</p>;
  return <div className="grid gap-4">
    {relationships.length > 1 && <label className="grid gap-1 text-sm text-stone-700">Therapist
      <select value={selected} onChange={event => setSelected(Number(event.target.value))} className="cursor-grab rounded-xl border border-stone-300 bg-white p-3 active:cursor-grabbing">
        {relationships.map((relationship, index) => <option key={`${relationship.clientId}:${relationship.practitionerId}`} value={index}>{relationship.therapistName}</option>)}
      </select>
    </label>}
    <ClientDocuments recordContext={relationships[selected]} />
  </div>;
}
