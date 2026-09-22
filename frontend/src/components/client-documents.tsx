"use client";

import Image from "next/image";
import { useEffect, useState } from "react";
import { LoadingSpinner } from "@/components/loading-spinner";

type RecordContext = { organizationId: string; clientId: string };
type DocumentWorkflowStatus = "draft" | "pending_signature" | "completed" | "signed";
type DocumentRecord = { id: string; title: string; documentType: string; filename: string; version: number; createdAt: string; contentType: string; byteSize: number | null; workflowStatus: DocumentWorkflowStatus; pageCount: number; contentUrl: string; thumbnailUrl: string | null; pageUrls: string[] };

function GridIcon() { return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path d="M4.5 4.5h6v6h-6zm9 0h6v6h-6zm-9 9h6v6h-6zm9 0h6v6h-6z" /></svg>; }
function ListIcon() { return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" d="M9 6h10.5M9 12h10.5M9 18h10.5" /><path d="M4.5 4.5h3v3h-3zm0 6h3v3h-3zm0 6h3v3h-3z" /></svg>; }
function DownloadIcon() { return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M12 3.75v11.5m0 0 4-4m-4 4-4-4M5.25 19.5h13.5" /></svg>; }
function CloseIcon() { return <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" d="m6 6 12 12M18 6 6 18" /></svg>; }
function DocumentIcon() { return <svg aria-hidden="true" className="size-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3.75h7.5l3 3v13.5H6.75V3.75Z" /><path strokeLinecap="round" d="M9 11.25h6m-6 3h6m-6 3h3.75" /></svg>; }

function labelFor(type: string) { return type === "consent_form" ? "Consent form" : type.replaceAll("_", " "); }
function sizeFor(bytes: number | null) { return bytes ? `${Math.max(1, Math.round(bytes / 1024))} KB` : "PDF"; }
function statusFor(status: DocumentWorkflowStatus | undefined) { return (status ?? "draft").replaceAll("_", " "); }

function Thumbnail({ document, sizes }: { document: DocumentRecord; sizes: string }) {
  return document.thumbnailUrl
    ? <Image src={document.thumbnailUrl} alt={`Preview of ${document.title}`} fill sizes={sizes} unoptimized className="object-cover object-top" />
    : <span className="grid size-full place-items-center text-stone-400"><DocumentIcon /></span>;
}

function DownloadLink({ document }: { document: DocumentRecord }) {
  return <a href={document.contentUrl} download={document.filename} onClick={event => event.stopPropagation()} title={`Download ${document.title}`} className="absolute right-3 top-3 z-20 grid size-9 cursor-grab place-items-center rounded-lg border border-stone-300 bg-white text-stone-700 opacity-0 shadow-sm transition-[opacity,color,background-color,border-color] duration-200 hover:border-emerald-800 hover:bg-emerald-800 hover:text-white focus:opacity-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 group-hover:border-emerald-800 group-hover:bg-emerald-800 group-hover:text-white group-hover:opacity-100 group-focus-within:opacity-100 active:cursor-grabbing"><span className="sr-only">Download {document.title}</span><DownloadIcon /></a>;
}

export function ClientDocuments({ recordContext }: { recordContext: RecordContext }) {
  const [view, setView] = useState<"grid" | "list">("grid");
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selected, setSelected] = useState<DocumentRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const query = new URLSearchParams({ organization_id: recordContext.organizationId });
    void fetch(`/api/clinical-records/clients/${recordContext.clientId}/documents?${query}`, { cache: "no-store" }).then(async response => {
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Could not load documents.");
      if (active) setDocuments(body.documents ?? []);
    }).catch((reason: Error) => { if (active) setError(reason.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [recordContext.clientId, recordContext.organizationId]);

  useEffect(() => {
    if (!selected) return;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setSelected(null); };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [selected]);

  return <section className="rounded-2xl border border-stone-200 bg-stone-100 p-2 text-left shadow-sm" aria-labelledby="documents-heading">
    <div className="rounded-xl border border-stone-200 bg-white p-6">
      <div className="flex items-center justify-between gap-4">
        <h2 id="documents-heading" className="text-lg font-semibold text-stone-900">Documents</h2>
        <div className="inline-flex rounded-lg border border-stone-300 bg-stone-100 p-1" aria-label="Document view">
          <button type="button" onClick={() => setView("grid")} aria-pressed={view === "grid"} title="Grid view" className={`grid size-8 cursor-grab place-items-center rounded-md active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${view === "grid" ? "bg-white text-emerald-800 shadow-sm" : "text-stone-500 hover:text-stone-800"}`}><span className="sr-only">Grid view</span><GridIcon /></button>
          <button type="button" onClick={() => setView("list")} aria-pressed={view === "list"} title="List view" className={`grid size-8 cursor-grab place-items-center rounded-md active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${view === "list" ? "bg-white text-emerald-800 shadow-sm" : "text-stone-500 hover:text-stone-800"}`}><span className="sr-only">List view</span><ListIcon /></button>
        </div>
      </div>

      {loading ? <LoadingSpinner label="Loading documents…" /> : error ? <p role="alert" className="mt-5 text-sm text-red-700">{error}</p> : documents.length === 0 ? <div className="mt-5 rounded-xl border border-stone-200 bg-stone-50 p-5 text-sm text-stone-600">No documents have been added.</div> : view === "grid" ? <div className="mt-5 grid grid-cols-[repeat(auto-fill,minmax(250px,310px))] gap-5">
        {documents.map(document => <article key={document.id} className="group relative overflow-hidden rounded-xl border border-stone-200 bg-white shadow-sm transition-colors duration-200 hover:border-stone-300">
          <button type="button" onClick={() => setSelected(document)} className="relative z-0 block w-full cursor-grab text-left active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-emerald-700">
            <div className="relative aspect-[8.5/11] overflow-hidden bg-stone-100"><Thumbnail document={document} sizes="310px" /></div>
            <div className="border-t border-stone-200 p-4"><h3 className="line-clamp-2 text-sm font-semibold text-stone-900">{document.title}</h3><p className="mt-1 text-xs capitalize text-stone-500">{labelFor(document.documentType)} · {statusFor(document.workflowStatus)} · PDF · {sizeFor(document.byteSize)}</p></div>
          </button><span aria-hidden="true" className="pointer-events-none absolute inset-0 z-10 bg-emerald-800/5 opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-within:opacity-100" /><DownloadLink document={document} />
        </article>)}
      </div> : <div className="mt-5 grid gap-2">
        {documents.map(document => <article key={document.id} className="group relative flex min-h-28 items-center overflow-hidden rounded-xl border border-stone-200 bg-stone-50 transition-colors duration-200 hover:border-stone-300">
          <button type="button" onClick={() => setSelected(document)} className="relative z-0 flex min-w-0 flex-1 cursor-grab items-center gap-4 p-3 pr-14 text-left active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-emerald-700">
            <div className="relative aspect-[8.5/11] h-24 shrink-0 overflow-hidden rounded-md border border-stone-200 bg-white"><Thumbnail document={document} sizes="75px" /></div>
            <div className="min-w-0"><h3 className="truncate text-sm font-semibold text-stone-900">{document.title}</h3><p className="mt-1 text-xs capitalize text-stone-500">{labelFor(document.documentType)} · {statusFor(document.workflowStatus)} · PDF · {sizeFor(document.byteSize)}</p></div>
          </button><span aria-hidden="true" className="pointer-events-none absolute inset-0 z-10 bg-emerald-800/5 opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-within:opacity-100" /><DownloadLink document={document} />
        </article>)}
      </div>}
    </div>

    {selected ? <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/55 p-3 backdrop-blur-sm sm:p-6" role="dialog" aria-modal="true" aria-labelledby="document-preview-title" onMouseDown={event => { if (event.target === event.currentTarget) setSelected(null); }}>
      <div className="flex h-[min(92vh,980px)] w-[min(96vw,1120px)] flex-col overflow-hidden rounded-2xl border border-stone-300 bg-white shadow-2xl">
        <div className="flex items-center gap-3 border-b border-stone-200 px-4 py-3">
          <h2 id="document-preview-title" className="min-w-0 flex-1 truncate text-sm font-semibold text-stone-900">{selected.title}</h2>
          <a href={selected.contentUrl} download={selected.filename} className="inline-flex cursor-grab items-center gap-2 rounded-lg border border-stone-300 px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing"><DownloadIcon />Download</a>
          <button type="button" onClick={() => setSelected(null)} aria-label="Close document preview" title="Close" className="grid size-9 cursor-grab place-items-center rounded-lg text-stone-600 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing"><CloseIcon /></button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto bg-stone-200 p-3 sm:p-6">
          {(selected.pageUrls ?? []).length ? <div className="mx-auto grid max-w-[900px] gap-4">
            {(selected.pageUrls ?? []).map((pageUrl, index) => <div key={pageUrl} className="overflow-hidden rounded-sm bg-white shadow-md">
              <Image src={pageUrl} alt={`${selected.title}, page ${index + 1} of ${selected.pageCount ?? selected.pageUrls.length}`} width={1100} height={1424} unoptimized className="h-auto w-full" />
            </div>)}
          </div> : <div className="mx-auto mt-10 max-w-md rounded-xl border border-stone-300 bg-white p-5 text-center text-sm text-stone-700">A page preview is not available for this document. Use Download to open the original PDF.</div>}
        </div>
      </div>
    </div> : null}
  </section>;
}
