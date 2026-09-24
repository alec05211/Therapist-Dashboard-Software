"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { LoadingSpinner } from "@/components/loading-spinner";

type RecordContext = { organizationId: string; clientId: string; practitionerId?: string };
type DocumentWorkflowStatus = "draft" | "pending_signature" | "completed" | "signed";
type DocumentRecord = { id: string; title: string; documentType: string; filename: string; version: number; createdAt: string; contentType: string; byteSize: number | null; workflowStatus: DocumentWorkflowStatus; pageCount: number; contentUrl: string; thumbnailUrl: string | null; pageUrls: string[]; signedPageUrls: string[]; signedUrl: string | null; signedAt: string | null; signerName: string | null };

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
    ? <Image src={document.thumbnailUrl} alt={`Preview of ${document.title}`} fill sizes={sizes} unoptimized style={{ colorScheme: "only light" }} className="object-cover object-top" />
    : <span className="grid size-full place-items-center text-stone-400"><DocumentIcon /></span>;
}

function DownloadLink({ document }: { document: DocumentRecord }) {
  return <a href={document.signedUrl ?? document.contentUrl} download={`${document.signedUrl ? "signed-" : ""}${document.filename}`} onClick={event => event.stopPropagation()} title={`Download ${document.title}`} className="document-download absolute right-3 top-3 z-20 grid size-9 cursor-grab place-items-center rounded-lg border opacity-100 shadow-sm transition-[background-color,box-shadow] duration-200 group-hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing"><span className="sr-only">Download {document.title}</span><DownloadIcon /></a>;
}

function UploadDocumentCard({ view, disabled, expanded, onClick }: { view: "grid" | "list"; disabled: boolean; expanded: boolean; onClick: () => void }) {
  return <button type="button" disabled={disabled} onClick={onClick} aria-expanded={expanded} aria-controls="document-upload-form" className={`group cursor-grab overflow-hidden rounded-xl border border-stone-300 bg-white text-left shadow-sm transition duration-200 ease-out hover:border-emerald-700 hover:shadow-md active:cursor-grabbing disabled:cursor-wait disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${view === "list" ? "flex min-h-[122px] items-center gap-4 p-3" : "w-full"}`}>
    <span className={`grid place-items-center bg-stone-100 transition-colors duration-200 group-hover:bg-emerald-50 ${view === "grid" ? "aspect-[8.5/11] w-full" : "h-24 w-[74px] shrink-0 rounded-md"}`}>
      <span className="grid size-16 place-items-center rounded-full border border-stone-300 bg-white text-emerald-800 shadow-sm transition-transform duration-200 ease-out group-hover:scale-105 motion-reduce:transform-none">
        <svg aria-hidden="true" className="size-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4m0 0L7 9m5-5 5 5M4 15v5h16v-5" /></svg>
      </span>
    </span>
    <span className={`block text-sm font-semibold text-stone-900 ${view === "grid" ? "h-24 border-t border-stone-200 p-4" : ""}`}>Upload Document</span>
  </button>;
}

function DocumentPage({ url, title, number }: { url: string; title: string; number: number }) {
  const [failed, setFailed] = useState(false);
  return failed ? <p role="alert" className="rounded-xl border border-stone-300 bg-white p-4 text-sm text-red-700">Page {number} could not be loaded. Close and reopen this document to retry, or download it to read the full PDF.</p>
    : <Image src={url} alt={`${title}, page ${number}`} width={1100} height={1424} unoptimized loading={number === 1 ? "eager" : "lazy"} decoding="sync" style={{ colorScheme: "only light", backgroundColor: "#fff" }} onError={() => setFailed(true)} className="h-auto w-full shadow-sm" />;
}

export function ClientDocuments({ recordContext }: { recordContext: RecordContext }) {
  return <DocumentSpace key={`${recordContext.organizationId}:${recordContext.clientId}:${recordContext.practitionerId ?? ""}`} recordContext={recordContext} />;
}

function DocumentSpace({ recordContext }: { recordContext: RecordContext }) {
  const [view, setView] = useState<"grid" | "list">("grid");
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [selected, setSelected] = useState<DocumentRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [revision, setRevision] = useState(0);
  const [canUpload, setCanUpload] = useState(false);
  const [canSign, setCanSign] = useState(false);
  const [practitionerId, setPractitionerId] = useState(recordContext.practitionerId);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showSigned, setShowSigned] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const control = "cursor-grab rounded-xl border border-stone-300 px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-100 active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700";
  const input = "w-full rounded-xl border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900";
  const query = new URLSearchParams({ organization_id: recordContext.organizationId });
  if (practitionerId) query.set("practitioner_id", practitionerId);
  const endpoint = `/api/clinical-records/clients/${recordContext.clientId}/documents`;

  async function mutate(url: string, body: FormData | string) {
    setBusy(true); setActionError(null); setNotice(null);
    try {
      const response = await fetch(url, { method: "POST", body, headers: typeof body === "string" ? { "Content-Type": "application/json" } : undefined });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Check the document details and try again.");
      setSelected(null); setUploadOpen(false); setRevision(value => value + 1);
      setNotice(typeof body === "string" ? "Signed copy saved in this document space." : "Document uploaded and shared with this client.");
    } catch (reason) { setActionError(reason instanceof Error ? reason.message : "Could not save the document."); }
    finally { setBusy(false); }
  }

  useEffect(() => {
    let active = true;
    const query = new URLSearchParams({ organization_id: recordContext.organizationId });
    if (recordContext.practitionerId) query.set("practitioner_id", recordContext.practitionerId);
    void fetch(`/api/clinical-records/clients/${recordContext.clientId}/documents?${query}`, { cache: "no-store" }).then(async response => {
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Could not load documents.");
      if (active) { setDocuments(body.documents ?? []); setCanUpload(body.canUpload); setCanSign(body.canSign); setPractitionerId(body.practitionerId); setError(null); }
    }).catch((reason: Error) => { if (active) setError(reason.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [recordContext.clientId, recordContext.organizationId, recordContext.practitionerId, revision]);

  useEffect(() => {
    const refresh = () => { if (!busy) setRevision(value => value + 1); };
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [busy]);

  useEffect(() => {
    if (selected) dialog.current?.showModal();
  }, [selected]);

  return <section className="rounded-2xl border border-stone-200 bg-stone-100 p-2 text-left shadow-sm" aria-labelledby="documents-heading">
    <div className="rounded-xl border border-stone-200 bg-white p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 id="documents-heading" className="text-lg font-semibold text-stone-900">Documents</h2>
        <div className="flex items-center gap-2"><div className="inline-flex rounded-lg border border-stone-300 bg-stone-100 p-1" aria-label="Document view">
          <button type="button" onClick={() => setView("grid")} aria-pressed={view === "grid"} title="Grid view" className={`grid size-8 cursor-grab place-items-center rounded-md active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${view === "grid" ? "bg-white text-emerald-800 shadow-sm" : "text-stone-500 hover:text-stone-800"}`}><span className="sr-only">Grid view</span><GridIcon /></button>
          <button type="button" onClick={() => setView("list")} aria-pressed={view === "list"} title="List view" className={`grid size-8 cursor-grab place-items-center rounded-md active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${view === "list" ? "bg-white text-emerald-800 shadow-sm" : "text-stone-500 hover:text-stone-800"}`}><span className="sr-only">List view</span><ListIcon /></button>
        </div></div>
      </div>
      {notice && <p role="status" className="mt-4 text-sm text-emerald-800">{notice}</p>}
      {actionError && !selected && <p role="alert" className="mt-4 text-sm text-red-700">{actionError}</p>}
      {uploadOpen && <form id="document-upload-form" className="mt-5 grid gap-4 rounded-xl border border-stone-200 bg-stone-50 p-4" onSubmit={event => {
        event.preventDefault(); const body = new FormData(event.currentTarget); const file = body.get("file");
        if (!(file instanceof File) || !file.size || file.size > 20 * 1024 * 1024) { setActionError("Choose a PDF smaller than 20 MB."); return; }
        void mutate(`${endpoint}?${query}`, body);
      }}>
        <label className="grid gap-1 text-sm text-stone-700">Title<input name="title" required maxLength={200} className={input} disabled={busy} /></label>
        <label className="grid gap-1 text-sm text-stone-700">PDF (up to 20 MB)<input name="file" type="file" accept="application/pdf,.pdf" required disabled={busy} className={input} /></label>
        <label className="flex items-center gap-2 text-sm text-stone-700"><input name="request_signature" type="checkbox" value="true" disabled={busy} className="cursor-grab active:cursor-grabbing" />Request the client&rsquo;s signature</label>
        <p className="text-sm text-stone-600">This document will be shared with the client in this relationship.</p>
        <div className="flex gap-2"><button className={control} disabled={busy}>{busy ? "Uploading..." : "Upload and share"}</button><button type="button" className={control} disabled={busy} onClick={() => setUploadOpen(false)}>Cancel</button></div>
      </form>}

      {loading ? <LoadingSpinner label="Loading documents…" /> : error ? <p role="alert" className="mt-5 text-sm text-red-700">{error}</p> : documents.length === 0 && !canUpload ? <div className="mt-5 rounded-xl border border-stone-200 bg-stone-50 p-5 text-sm text-stone-600">No documents have been added.</div> : view === "grid" ? <div className="mt-5 grid grid-cols-[repeat(auto-fill,minmax(min(100%,250px),310px))] gap-5">
        {canUpload && <UploadDocumentCard view={view} disabled={busy} expanded={uploadOpen} onClick={() => { setUploadOpen(value => !value); setActionError(null); }} />}
        {documents.map(document => <article key={document.id} className="group relative overflow-hidden rounded-xl border border-stone-200 bg-white shadow-sm transition-colors duration-200 hover:border-stone-300">
          <button type="button" onClick={() => { setActionError(null); setShowSigned(Boolean(document.signedUrl)); setSelected(document); }} className="relative z-0 block w-full cursor-grab text-left active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-emerald-700">
            <div className="relative aspect-[8.5/11] overflow-hidden bg-stone-100"><Thumbnail document={document} sizes="310px" /></div>
            <div className="h-24 border-t border-stone-200 p-4"><h3 className="line-clamp-2 text-sm font-semibold text-stone-900">{document.title}</h3><p className="mt-1 text-xs capitalize text-stone-500">{labelFor(document.documentType)} · {statusFor(document.workflowStatus)} · PDF · {sizeFor(document.byteSize)}</p></div>
          </button><span aria-hidden="true" className="pointer-events-none absolute inset-0 z-10 bg-emerald-800/5 opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-within:opacity-100" /><DownloadLink document={document} />
        </article>)}
      </div> : <div className="mt-5 grid gap-2">
        {canUpload && <UploadDocumentCard view={view} disabled={busy} expanded={uploadOpen} onClick={() => { setUploadOpen(value => !value); setActionError(null); }} />}
        {documents.map(document => <article key={document.id} className="group relative flex min-h-28 items-center overflow-hidden rounded-xl border border-stone-200 bg-stone-50 transition-colors duration-200 hover:border-stone-300">
          <button type="button" onClick={() => { setActionError(null); setShowSigned(Boolean(document.signedUrl)); setSelected(document); }} className="relative z-0 flex min-w-0 flex-1 cursor-grab items-center gap-4 p-3 pr-14 text-left active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-emerald-700">
            <div className="relative aspect-[8.5/11] h-24 shrink-0 overflow-hidden rounded-md border border-stone-200 bg-white"><Thumbnail document={document} sizes="75px" /></div>
            <div className="min-w-0"><h3 className="truncate text-sm font-semibold text-stone-900">{document.title}</h3><p className="mt-1 text-xs capitalize text-stone-500">{labelFor(document.documentType)} · {statusFor(document.workflowStatus)} · PDF · {sizeFor(document.byteSize)}</p></div>
          </button><span aria-hidden="true" className="pointer-events-none absolute inset-0 z-10 bg-emerald-800/5 opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-within:opacity-100" /><DownloadLink document={document} />
        </article>)}
      </div>}
    </div>

    {selected ? <dialog ref={dialog} onCancel={event => { if (busy) event.preventDefault(); else setSelected(null); }} onClose={() => { if (!busy) setSelected(null); }} className="m-auto h-[92vh] w-[96vw] max-w-[1120px] rounded-2xl border border-stone-300 bg-white p-0 text-stone-900 shadow-2xl backdrop:bg-stone-950/55" aria-labelledby="document-preview-title">
      <div className="flex h-full flex-col">
        <div className="flex flex-wrap items-center gap-3 border-b border-stone-200 px-4 py-3">
          <h2 id="document-preview-title" className="min-w-0 flex-1 text-sm font-semibold">{selected.title}</h2>
          {selected.signedUrl && <button type="button" className={control} onClick={() => setShowSigned(value => !value)}>{showSigned ? "View original" : "View signed copy"}</button>}
          <a href={showSigned && selected.signedUrl ? selected.signedUrl : selected.contentUrl} download={`${showSigned ? "signed-" : ""}${selected.filename}`} className={control}>Download</a>
          <button type="button" onClick={() => setSelected(null)} disabled={busy} aria-label="Close document preview" className={control}><CloseIcon /></button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto bg-stone-200 p-3 sm:p-6">
          {(showSigned ? selected.signedPageUrls : selected.pageUrls)?.length ? <div className="mx-auto grid max-w-[900px] gap-4">
            {(showSigned ? selected.signedPageUrls : selected.pageUrls).map((url, index) => <DocumentPage key={url} url={url} title={selected.title} number={index + 1} />)}
          </div> : <p className="rounded-xl border border-stone-300 bg-white p-5 text-sm text-stone-700">A page preview is unavailable. Download this document to read it before signing.</p>}
        </div>
        {selected.signedAt && <p className="border-t border-stone-200 p-4 text-sm text-stone-600">Signed by {selected.signerName}  |  {new Date(selected.signedAt).toLocaleString()}</p>}
        {canSign && selected.workflowStatus === "pending_signature" && <form className="grid max-h-[45vh] gap-3 overflow-auto border-t border-stone-200 p-4" onSubmit={event => {
          event.preventDefault(); const data = new FormData(event.currentTarget);
          void mutate(`${endpoint}/${selected.id}/sign?${query}`, JSON.stringify({ name: data.get("name"), consent: data.get("consent") === "on" }));
        }}>
          <label className="grid gap-1 text-sm">Your full name<input name="name" required maxLength={120} autoComplete="name" disabled={busy} className={input} /></label>
          <label className="flex items-start gap-2 text-sm text-stone-700"><input name="consent" type="checkbox" required disabled={busy} className="mt-1 cursor-grab active:cursor-grabbing" />I have read this document and agree to sign it electronically using my typed name.</label>
          {actionError && <p role="alert" className="text-sm text-red-700">{actionError}</p>}
          <button type="submit" disabled={busy} className={control}>{busy ? "Saving signed copy..." : "Sign and save"}</button>
        </form>}
      </div>
    </dialog> : null}
  </section>;
}
