"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { LoadingSpinner } from "@/components/loading-spinner";
import { ChatIcon } from "@/components/care-relationship-header";

type Client = { id: string; organization_id: string; name: string | null; email: string | null; phone: string | null; status: string };

export function ClientList() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const response = await fetch("/api/therapist/clients", { cache: "no-store", signal });
      if (!response.ok) throw new Error(response.status === 403 ? "This page is available to therapists only." : response.status === 401 ? "Please sign in to view your clients." : "Could not load your clients. Please try again.");
      const body: { clients: Client[] } = await response.json();
      if (!signal?.aborted) setClients(body.clients);
    } catch (reason) {
      if (!signal?.aborted) { setClients([]); setError(reason instanceof Error ? reason.message : "Could not load your clients."); }
    } finally { if (!signal?.aborted) setLoading(false); }
  }, []);
  const retry = () => { setLoading(true); setError(null); void load(); };
  useEffect(() => {
    const controller = new AbortController();
    const reload = () => {
      if (controller.signal.aborted) return;
      setLoading(true);
      setError(null);
      void load(controller.signal);
    };
    const onVisible = () => { if (document.visibilityState === "visible") reload(); };
    void Promise.resolve().then(reload);
    window.addEventListener("pageshow", reload);
    document.addEventListener("visibilitychange", onVisible);
    return () => { controller.abort(); window.removeEventListener("pageshow", reload); document.removeEventListener("visibilitychange", onVisible); };
  }, [load]);
  const normalize = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const visible = clients.filter(client => normalize([client.name, client.email, client.phone].filter(Boolean).join(" ")).includes(normalize(query.trim())));

  return <main className="mx-auto w-[min(94vw,1200px)] py-8 sm:py-12">
    <div className="mb-6"><h1 className="text-2xl font-semibold tracking-tight text-stone-900">Client list</h1></div>
    <section aria-label="Your clients" aria-busy={loading} className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-stone-200 p-5">
        <label className="block w-full sm:max-w-sm"><span className="sr-only">Search clients</span><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search clients by name, email, or phone" className="block w-full rounded-xl border border-stone-300 bg-stone-50 px-3 py-2.5 text-sm text-stone-900 placeholder:text-stone-500 focus:outline-none focus-visible:border-stone-500" /></label>
        {!loading && !error && <p role="status" className="text-sm text-stone-600">{visible.length} of {clients.length} {clients.length === 1 ? "client" : "clients"}</p>}
      </div>
      {loading ? <div className="p-8"><LoadingSpinner label="Loading your clients…" /></div> : error ? <div role="alert" className="p-8"><p className="text-sm text-stone-700">{error}</p><button type="button" onClick={retry} className="mt-4 cursor-grab rounded-xl border border-stone-300 px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing">Try again</button></div> : visible.length === 0 ? <div className="p-8"><h2 className="font-semibold text-stone-900">{clients.length ? "No matching clients" : "No clients connected yet"}</h2><p className="mt-2 text-sm text-stone-600">{clients.length ? "Try a different name, email, or phone number." : "Clients will appear here when you have an active care connection."}</p></div> : <ul className="divide-y divide-stone-200">
        {visible.map(client => <li key={`${client.organization_id}:${client.id}`} className="flex items-center gap-2 pr-4 sm:pr-6"><Link href={`/clients/${encodeURIComponent(client.id)}`} prefetch={false} className="flex min-w-0 flex-1 cursor-grab flex-wrap items-center gap-4 p-5 transition-colors duration-200 hover:bg-stone-50 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-emerald-700 active:cursor-grabbing sm:p-6">
          <span aria-hidden="true" className="flex size-11 shrink-0 items-center justify-center rounded-full border border-stone-200 bg-stone-100 text-sm font-semibold text-stone-700">{(client.name || "Client").trim().split(/\s+/).map(part => part[0]).slice(0, 2).join("")}</span>
          <div className="min-w-0 flex-1"><h2 className="break-words font-semibold text-stone-900">{client.name || "Unnamed client"}</h2><div className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-sm text-stone-600">{client.email && <span className="break-all">{client.email}</span>}{client.phone && <span>{client.phone}</span>}{!client.email && !client.phone && <span>No contact details added</span>}</div></div>
          <span className="rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-xs font-medium capitalize text-stone-700">{client.status}</span><span aria-hidden="true" className="text-stone-500">→</span>
        </Link><Link href={`/clients/${encodeURIComponent(client.id)}?view=chat`} prefetch={false} aria-label={`Chat with ${client.name || "client"}`} className="inline-flex shrink-0 cursor-grab items-center gap-2 rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700 transition-colors duration-200 hover:border-stone-400 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing"><ChatIcon />Chat</Link></li>)}
      </ul>}
    </section>
  </main>;
}
