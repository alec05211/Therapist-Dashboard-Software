"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import type { Appointment } from "@/lib/types";
import styles from "./client-care-assistant.module.css";

export type AssistantChat = { id: string; title: string; messages: { role: "user" | "assistant"; text: string }[] };
type Relationship = { organizationId: string; clientId: string; practitionerId: string };
const circle = "grid size-10 shrink-0 cursor-grab place-items-center rounded-full border border-[var(--border)] bg-[var(--surface)] text-[var(--text-muted)] shadow-sm transition-colors duration-200 hover:bg-[var(--surface-inset)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-50";
const action = "cursor-grab rounded-lg text-left focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent-strong)] active:cursor-grabbing";

async function readJson(url: string, signal: AbortSignal) {
  const response = await fetch(url, { cache: "no-store", signal });
  if (!response.ok) throw new Error("Information unavailable");
  return response.json();
}

export function ClientCareAssistant({ appointments, scheduleError, chats, onChatsChange, onOpenWorkspace, onOpenDocuments }: {
  appointments?: Appointment[];
  scheduleError: boolean;
  chats: AssistantChat[];
  onChatsChange: (chats: AssistantChat[]) => void;
  onOpenWorkspace: () => void;
  onOpenDocuments: () => void;
}) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [draft, setDraft] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 });
  const [unread, setUnread] = useState<number | null>(null);
  const [pending, setPending] = useState<number | null>(null);
  const [overviewLoaded, setOverviewLoaded] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const history = useRef<HTMLDialogElement>(null);
  const composer = useRef<HTMLInputElement>(null);
  const latestMessage = useRef<HTMLDivElement>(null);
  const id = useId();
  const activeChat = chats.find(chat => chat.id === activeId);
  const messages = activeChat?.messages ?? [];
  const upcoming = appointments?.filter(appointment => ["scheduled", "confirmed"].includes(appointment.status) && new Date(appointment.ends_at).getTime() > now)
    .sort((a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime())[0];

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let controller: AbortController;
    const refresh = () => {
      controller?.abort();
      controller = new AbortController();
      const signal = controller.signal;
      void Promise.allSettled([
        readJson("/api/inbox", signal).then(body => {
          if (!signal.aborted) setUnread(typeof body.unreadCount === "number" ? body.unreadCount : null);
        }).catch(() => { if (!signal.aborted) setUnread(null); }),
        readJson("/api/document-relationships", signal).then(async body => {
          const relationships = body.relationships as Relationship[];
          const results = await Promise.all(relationships.map(async relationship => {
            const query = new URLSearchParams({ organization_id: relationship.organizationId, practitioner_id: relationship.practitionerId });
            const result = await readJson(`/api/clinical-records/clients/${encodeURIComponent(relationship.clientId)}/documents?${query}`, signal);
            return (result.documents as { workflowStatus: string }[]).filter(document => document.workflowStatus === "pending_signature").length;
          }));
          if (!signal.aborted) setPending(results.reduce((sum, count) => sum + count, 0));
        }).catch(() => { if (!signal.aborted) setPending(null); }),
      ]).then(() => { if (!signal.aborted) setOverviewLoaded(true); });
    };
    refresh();
    window.addEventListener("focus", refresh);
    window.addEventListener("inbox-changed", refresh);
    return () => { controller.abort(); window.removeEventListener("focus", refresh); window.removeEventListener("inbox-changed", refresh); };
  }, []);

  useEffect(() => {
    latestMessage.current?.scrollIntoView({ block: "nearest", behavior: "instant" });
  }, [messages.length, activeId]);

  function closeHistory() {
    history.current?.close();
    setMenuOpen(false);
    trigger.current?.focus();
  }

  function openHistory() {
    const rect = trigger.current?.getBoundingClientRect();
    if (rect) setMenuPosition({ top: Math.max(12, Math.min(rect.top - 12, window.innerHeight - 180)), left: Math.max(12, Math.min(rect.left - 12, window.innerWidth - 372)) });
    history.current?.showModal();
    setMenuOpen(true);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    const chat = activeChat ?? { id: crypto.randomUUID(), title: text.slice(0, 70), messages: [] };
    const updated: AssistantChat = { ...chat, messages: [...chat.messages,
      { role: "user", text }, { role: "assistant", text: "AI chat is not connected yet. This message is a local preview." }] };
    onChatsChange([updated, ...chats.filter(item => item.id !== chat.id)]);
    setActiveId(chat.id);
    setDraft("");
    composer.current?.focus();
  }

  return <section aria-label="Care assistant" className="flex min-h-[min(480px,65svh)] flex-col rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5">
    <header className="flex items-center justify-between gap-3">
      <button ref={trigger} type="button" aria-label="Open chat history" aria-haspopup="dialog" aria-expanded={menuOpen} aria-controls={`${id}-history`} onClick={openHistory} className={circle}>
        <svg aria-hidden="true" className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" d="M5 7h14M5 12h10M5 17h14" /></svg>
      </button>
      <span title="AI is not connected. Chats are kept only until this page reloads." className="text-xs text-[var(--text-muted)]">Preview</span>
    </header>

    {messages.length === 0 ? <div className={`${styles.engraved} mx-auto flex w-full max-w-lg flex-1 flex-col justify-center gap-7 px-2 py-9 sm:px-5 sm:py-12`}>
      <button type="button" onClick={onOpenWorkspace} className={action}>
        <span className="block text-sm">Next session</span>
        <span className="mt-1 block text-2xl font-medium tracking-tight sm:text-3xl">{upcoming ? new Date(upcoming.starts_at).toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" }) : scheduleError ? "Schedule unavailable" : appointments ? "Nothing scheduled" : "Loading…"}</span>
        {upcoming && <span className="mt-2 block text-sm">{new Date(upcoming.starts_at).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZoneName: "short" })} · {({ in_person: "In person", video: "Video", phone: "Phone" })[upcoming.meeting_mode]}</span>}
      </button>
      <div className="flex flex-col gap-3 border-t border-[var(--border)] pt-5 text-sm">
        {!overviewLoaded ? <p role="status">Loading your updates…</p> : <>
          {pending !== null && pending > 0 && <button type="button" onClick={onOpenDocuments} className={action}>{pending} {pending === 1 ? "document needs" : "documents need"} your signature <span aria-hidden="true">↗</span></button>}
          {unread !== null && unread > 0 && <Link href="/inbox" className={action}>{unread} unread {unread === 1 ? "notification" : "notifications"} <span aria-hidden="true">↗</span></Link>}
          {pending === 0 && unread === 0 && <p>You’re all caught up.</p>}
          {(pending === null || unread === null) && <p className="text-xs">Some updates are unavailable.</p>}
        </>}
      </div>
    </div> : <div role="log" aria-label="Conversation preview" aria-live="polite" aria-relevant="additions" className="flex-1 space-y-5 px-1 py-7 sm:px-4">
      {messages.map((message, index) => <div key={index} ref={index === messages.length - 1 ? latestMessage : undefined} className={`max-w-2xl text-sm leading-6 ${message.role === "user" ? "ml-auto w-fit rounded-2xl bg-[var(--surface-inset)] px-4 py-2.5" : "text-[var(--text-muted)]"}`}>
        <span className="sr-only">{message.role === "user" ? "You: " : "Assistant preview: "}</span><p className="whitespace-pre-wrap break-words">{message.text}</p>
      </div>)}
    </div>}

    <form onSubmit={submit} className="flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--surface-subtle)] p-1.5 pl-5 focus-within:border-[var(--border-strong)]">
      <input ref={composer} aria-label="Message care assistant" aria-describedby={`${id}-notice`} value={draft} onChange={event => setDraft(event.target.value)} maxLength={2000} placeholder="Message…" className="h-10 min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-[var(--text-muted)] sm:text-sm" />
      <button type="submit" disabled={!draft.trim()} aria-label="Send preview message" title="Send message" className="grid size-10 shrink-0 cursor-grab place-items-center rounded-full bg-[var(--accent-strong)] text-white transition-colors hover:bg-[var(--accent-strong-hover)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-50">
        <svg aria-hidden="true" className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M12 17V5m-5 5 5-5 5 5M5 17v3h14v-3" /></svg>
      </button>
    </form>
    <p id={`${id}-notice`} className="sr-only">Local preview. AI is not connected. Not monitored by your therapist. Chats are cleared on reload.</p>

    <dialog ref={history} id={`${id}-history`} aria-labelledby={`${id}-history-title`} onCancel={() => setMenuOpen(false)} onClose={() => setMenuOpen(false)} onClick={event => {
      if (event.target === event.currentTarget) {
        const rect = event.currentTarget.getBoundingClientRect();
        if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeHistory();
      }
    }} style={{ top: menuPosition.top, left: menuPosition.left, maxHeight: `calc(100svh - ${menuPosition.top + 12}px)` }} className={styles.history}>
      <div className="flex items-center justify-between gap-3 p-3">
        <button type="button" autoFocus aria-label="Close chat history" onClick={closeHistory} className={circle}><svg aria-hidden="true" className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" d="m6 6 12 12M18 6 6 18" /></svg></button>
        <h2 id={`${id}-history-title`} className="mr-auto text-sm font-semibold">Past chats</h2>
      </div>
      <div className={`${styles.historyContent} border-t border-[var(--border)] p-3`}>
        <button type="button" className="w-full cursor-grab rounded-xl bg-[var(--accent-surface)] px-4 py-3 text-left text-sm font-medium text-[var(--accent-text)] hover:bg-[var(--accent-surface-hover)] focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)] active:cursor-grabbing" onClick={() => { setActiveId(null); setDraft(""); closeHistory(); composer.current?.focus(); }}>+ New chat</button>
        <nav aria-label="Past chats" className="mt-2 space-y-1">
          {chats.map(chat => <button key={chat.id} type="button" aria-current={chat.id === activeId ? "page" : undefined} className={`block w-full cursor-grab truncate rounded-xl px-4 py-3 text-left text-sm hover:bg-[var(--surface-inset)] focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)] active:cursor-grabbing ${chat.id === activeId ? "bg-[var(--surface-inset)]" : ""}`} onClick={() => { setActiveId(chat.id); setDraft(""); closeHistory(); }}>{chat.title}</button>)}
        </nav>
        <p className="px-4 pb-1 pt-4 text-xs text-[var(--text-muted)]">{chats.length ? "Chats stay until you reload." : "No chats yet."}</p>
      </div>
    </dialog>
  </section>;
}
