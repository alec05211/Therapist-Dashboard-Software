"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { LoadingSpinner } from "@/components/loading-spinner";
import { ChatIcon } from "@/components/care-relationship-header";

type Client = { id: string; organization_id: string; name: string | null; email: string | null; phone: string | null; status: string };
type DirectoryClient = { id: string; name: string | null; email: string | null; phone: string | null; photoUrl: string | null };

export function ClientList() {
  const router = useRouter();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [directoryQuery, setDirectoryQuery] = useState("");
  const [directoryClients, setDirectoryClients] = useState<DirectoryClient[]>([]);
  const [directoryLoading, setDirectoryLoading] = useState(false);
  const [directoryError, setDirectoryError] = useState<string | null>(null);
  const [addingId, setAddingId] = useState<string | null>(null);
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
  useEffect(() => {
    if (!addOpen) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setDirectoryLoading(true); setDirectoryError(null);
      void fetch(`/api/therapist/client-directory?query=${encodeURIComponent(directoryQuery.trim())}`, { cache: "no-store", signal: controller.signal })
        .then(async response => { const body = await response.json(); if (!response.ok) throw new Error(body.detail || "Could not search client accounts."); setDirectoryClients(body.clients || []); })
        .catch(reason => { if (!controller.signal.aborted) setDirectoryError(reason instanceof Error ? reason.message : "Could not search client accounts."); })
        .finally(() => { if (!controller.signal.aborted) setDirectoryLoading(false); });
    }, 180);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [addOpen, directoryQuery]);

  const addClient = async (client: DirectoryClient) => {
    if (addingId) return;
    setAddingId(client.id); setDirectoryError(null);
    try {
      const response = await fetch(`/api/therapist/clients/${encodeURIComponent(client.id)}`, { method: "POST" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Could not add this client.");
      router.push(`/clients/${encodeURIComponent(client.id)}`);
    } catch (reason) { setDirectoryError(reason instanceof Error ? reason.message : "Could not add this client."); setAddingId(null); }
  };
  const normalize = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const visible = clients.filter(client => normalize([client.name, client.email, client.phone].filter(Boolean).join(" ")).includes(normalize(query.trim())));

  return <main className="mx-auto w-[min(94vw,1200px)] py-8 sm:py-12">
    <div className="mb-6 flex items-center justify-between gap-4"><h1 className="text-2xl font-semibold tracking-tight text-stone-900">Client list</h1><button type="button" onClick={() => setAddOpen(true)} className="cursor-grab rounded-xl bg-emerald-800 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-900 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Add client</button></div>
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
    {addOpen ? <div role="presentation" onMouseDown={event => { if (event.target === event.currentTarget && !addingId) setAddOpen(false); }} className="fixed inset-0 z-50 grid place-items-center bg-stone-950/35 p-4 backdrop-blur-[3px]">
      <section role="dialog" aria-modal="true" aria-labelledby="add-client-title" className="w-full max-w-xl overflow-hidden rounded-2xl border border-stone-300 bg-white shadow-xl">
        <div className="flex items-center justify-between gap-4 border-b border-stone-300 p-5"><h2 id="add-client-title" className="text-lg font-semibold text-stone-900">Add an existing client</h2><button type="button" disabled={Boolean(addingId)} onClick={() => setAddOpen(false)} aria-label="Close client search" className="cursor-grab rounded-lg px-2 py-1 text-xl text-stone-500 hover:bg-stone-100 active:cursor-grabbing disabled:cursor-wait">×</button></div>
        <div className="p-5"><label><span className="sr-only">Search existing client accounts</span><input autoFocus type="search" value={directoryQuery} onChange={event => setDirectoryQuery(event.target.value)} placeholder="Search by name or email" className="w-full rounded-xl border border-stone-300 bg-stone-50 px-3 py-2.5 text-sm text-stone-900 placeholder:text-stone-500 focus:outline-none focus-visible:border-stone-500" /></label></div>
        <div className="max-h-80 overflow-y-auto border-t border-stone-200">
          {directoryLoading ? <div className="p-6"><LoadingSpinner label="Searching client accounts…" /></div> : directoryError ? <p role="alert" className="p-5 text-sm text-red-700">{directoryError}</p> : directoryClients.length ? <ul className="divide-y divide-stone-200">{directoryClients.map(client => <li key={client.id}><button type="button" disabled={Boolean(addingId)} onClick={() => void addClient(client)} className="flex w-full cursor-grab items-center gap-4 p-4 text-left hover:bg-stone-50 active:cursor-grabbing disabled:cursor-wait disabled:opacity-60">
            <span className="relative grid size-12 shrink-0 place-items-center overflow-hidden rounded-full border border-stone-300 bg-stone-100 text-sm font-semibold text-stone-700">{client.photoUrl ? <Image src={client.photoUrl} alt={`${client.name || "Client"} profile`} fill sizes="48px" unoptimized className="object-cover" /> : <span aria-hidden="true">{(client.name || "Client").split(/\s+/).map(part => part[0]).slice(0, 2).join("")}</span>}</span>
            <span className="min-w-0 flex-1"><strong className="block truncate text-sm text-stone-900">{client.name || "Unnamed client"}</strong><span className="mt-1 block truncate text-xs text-stone-600">{client.email || client.phone || "Existing client account"}</span></span><span className="text-sm font-semibold text-emerald-800">{addingId === client.id ? "Adding…" : "Add"}</span>
          </button></li>)}</ul> : <p className="p-6 text-sm text-stone-600">No unconnected client accounts match this search.</p>}
        </div>
      </section>
    </div> : null}
  </main>;
}
