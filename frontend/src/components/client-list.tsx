"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ChatIcon } from "@/components/care-relationship-header";
import { LoadingSpinner } from "@/components/loading-spinner";

type Client = { id: string; organization_id: string; name: string | null; email: string | null; phone: string | null; status: string; photoUrl: string | null };
type DirectoryClient = { id: string; kind: "client" | "registration"; relationship: "connected" | "available"; name: string | null; email: string | null; phone: string | null; photoUrl: string | null };

function Avatar({ person, size = "size-11" }: { person: { name: string | null; photoUrl: string | null }; size?: string }) {
  return <span className={`relative grid ${size} shrink-0 place-items-center overflow-hidden rounded-full border border-stone-200 bg-stone-100 text-sm font-semibold text-stone-700`}>
    {person.photoUrl ? <Image src={person.photoUrl} alt={`${person.name || "Client"} profile`} fill sizes="48px" unoptimized className="object-cover" /> : <span aria-hidden="true">{(person.name || "Client").trim().split(/\s+/).map(part => part[0]).slice(0, 2).join("")}</span>}
  </span>;
}

export function ClientList() {
  const router = useRouter();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<DirectoryClient[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
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

  useEffect(() => {
    const controller = new AbortController();
    const reload = () => { if (!controller.signal.aborted) { setLoading(true); setError(null); void load(controller.signal); } };
    const onVisible = () => { if (document.visibilityState === "visible") reload(); };
    void Promise.resolve().then(reload);
    window.addEventListener("pageshow", reload);
    document.addEventListener("visibilitychange", onVisible);
    return () => { controller.abort(); window.removeEventListener("pageshow", reload); document.removeEventListener("visibilitychange", onVisible); };
  }, [load]);

  useEffect(() => {
    const value = query.trim();
    if (!value) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setSearching(true); setSearchError(null);
      void fetch(`/api/therapist/client-directory?query=${encodeURIComponent(value)}`, { cache: "no-store", signal: controller.signal })
        .then(async response => { const body = await response.json(); if (!response.ok) throw new Error(body.detail || "Could not search client accounts."); setResults(body.clients || []); })
        .catch(reason => { if (!controller.signal.aborted) setSearchError(reason instanceof Error ? reason.message : "Could not search client accounts."); })
        .finally(() => { if (!controller.signal.aborted) setSearching(false); });
    }, 180);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [query]);

  const addClient = async (client: DirectoryClient) => {
    if (addingId) return;
    setAddingId(client.id); setSearchError(null); setNotice(null);
    try {
      const endpoint = client.kind === "registration" ? `/api/therapist/client-registrations/${encodeURIComponent(client.id)}/invite` : `/api/therapist/clients/${encodeURIComponent(client.id)}`;
      const response = await fetch(endpoint, { method: "POST" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Could not connect with this person.");
      if (client.kind === "registration") {
        setNotice(`Invitation sent to ${client.name || "this person"}.`);
        setResults(current => current.filter(item => item.id !== client.id));
        setAddingId(null);
      } else router.push(`/clients/${encodeURIComponent(body.client?.id || client.id)}`);
    } catch (reason) { setSearchError(reason instanceof Error ? reason.message : "Could not connect with this person."); setAddingId(null); }
  };

  const retry = () => { setLoading(true); setError(null); void load(); };
  const searchActive = Boolean(query.trim());

  return <main className="mx-auto w-[min(94vw,1200px)] pb-8 pt-3">
    <section aria-label="Clients and people search" aria-busy={loading || searching} className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-stone-200 p-5">
        <label className="block w-full sm:max-w-md"><span className="sr-only">Search clients and people</span><input type="search" value={query} onChange={event => { const value = event.target.value; setQuery(value); setNotice(null); if (!value.trim()) { setResults([]); setSearching(false); setSearchError(null); } }} placeholder="Search people by name or email" className="block w-full rounded-xl border border-stone-300 bg-stone-50 px-3 py-2.5 text-sm text-stone-900 placeholder:text-stone-500 focus:outline-none focus-visible:border-stone-500" /></label>
        {!loading && !error && !searchActive && <p role="status" className="text-sm text-stone-600">{clients.length} {clients.length === 1 ? "client" : "clients"}</p>}
        {!searching && searchActive && !searchError && <p role="status" className="text-sm text-stone-600">{results.length} {results.length === 1 ? "result" : "results"}</p>}
      </div>
      {notice && <p role="status" className="border-b border-stone-200 bg-emerald-50 px-5 py-3 text-sm font-medium text-emerald-800">{notice}</p>}
      {searchActive ? searching ? <div className="p-8"><LoadingSpinner label="Searching people…" /></div> : searchError ? <p role="alert" className="p-6 text-sm text-red-700">{searchError}</p> : results.length ? <ul className="divide-y divide-stone-200">{results.map(person => <li key={`${person.kind}:${person.id}`} className="flex items-center gap-3 px-5 py-4 sm:px-6">
        {person.relationship === "connected" ? <Link href={`/clients/${encodeURIComponent(person.id)}`} prefetch={false} className="flex min-w-0 flex-1 cursor-grab items-center gap-4 rounded-xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing"><Avatar person={person} size="size-12" /><span className="min-w-0 flex-1"><strong className="block truncate text-sm text-stone-900">{person.name || "Unnamed client"}</strong><span className="mt-1 block truncate text-xs text-stone-600">{person.email || person.phone || "Connected client"}</span></span><span className="text-sm font-semibold text-stone-600">Open</span></Link> : <button type="button" disabled={Boolean(addingId)} onClick={() => void addClient(person)} className="flex min-w-0 flex-1 cursor-grab items-center gap-4 rounded-xl text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing disabled:cursor-wait disabled:opacity-60"><Avatar person={person} size="size-12" /><span className="min-w-0 flex-1"><strong className="block truncate text-sm text-stone-900">{person.name || "Unnamed person"}</strong><span className="mt-1 block truncate text-xs text-stone-600">{person.email || person.phone || "Account available to connect"}</span></span><span className="text-sm font-semibold text-emerald-800">{addingId === person.id ? (person.kind === "registration" ? "Sending…" : "Adding…") : (person.kind === "registration" ? "Invite" : "Add")}</span></button>}
      </li>)}</ul> : <div className="p-8"><h2 className="font-semibold text-stone-900">No matching people</h2><p className="mt-2 text-sm text-stone-600">Try a different name or email address.</p></div> : loading ? <div className="p-8"><LoadingSpinner label="Loading your clients…" /></div> : error ? <div role="alert" className="p-8"><p className="text-sm text-stone-700">{error}</p><button type="button" onClick={retry} className="mt-4 cursor-grab rounded-xl border border-stone-300 px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing">Try again</button></div> : clients.length ? <ul className="divide-y divide-stone-200">
        {clients.map(client => <li key={`${client.organization_id}:${client.id}`} className="flex items-center gap-2 pr-4 sm:pr-6"><Link href={`/clients/${encodeURIComponent(client.id)}`} prefetch={false} className="flex min-w-0 flex-1 cursor-grab flex-wrap items-center gap-4 p-5 transition-colors duration-200 hover:bg-stone-50 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-emerald-700 active:cursor-grabbing sm:p-6"><Avatar person={client} /><div className="min-w-0 flex-1"><h2 className="break-words font-semibold text-stone-900">{client.name || "Unnamed client"}</h2><div className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-sm text-stone-600">{client.email && <span className="break-all">{client.email}</span>}{client.phone && <span>{client.phone}</span>}{!client.email && !client.phone && <span>No contact details added</span>}</div></div><span className="rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-xs font-medium capitalize text-stone-700">{client.status}</span><span aria-hidden="true" className="text-stone-500">→</span></Link><Link href={`/clients/${encodeURIComponent(client.id)}?view=chat`} prefetch={false} aria-label={`Chat with ${client.name || "client"}`} className="inline-flex shrink-0 cursor-grab items-center gap-2 rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700 transition-colors duration-200 hover:border-stone-400 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing"><ChatIcon />Chat</Link></li>)}
      </ul> : <div className="p-8"><h2 className="font-semibold text-stone-900">No clients connected yet</h2><p className="mt-2 text-sm text-stone-600">Search by name or email to invite someone.</p></div>}
    </section>
  </main>;
}
