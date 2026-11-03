"use client";

import { useState, type FormEvent } from "react";
import { ChatIcon } from "@/components/care-relationship-header";

type Message = { role: "user" | "assistant"; text: string };
const previewReply = "This is a conversation preview. AI responses and access to shared insights, appointments, and billing are not connected yet. You can find available information in your Clinical workspace and Billing tabs.";
const control = "cursor-grab rounded-xl border border-[var(--border)] px-3 py-2 text-sm hover:bg-[var(--surface-inset)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] active:cursor-grabbing";

export function ClientCareAssistant() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setMessages(current => [...current, { role: "user", text }, { role: "assistant", text: previewReply }]);
    setDraft("");
  }

  return <section aria-labelledby="care-assistant-title" className="rounded-2xl border border-[var(--border)] bg-[var(--settings-backcard)] p-3 text-left sm:p-4">
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-sm">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] p-4 sm:px-6">
        <div>
          <h2 id="care-assistant-title" className="flex items-center gap-2 text-lg font-semibold"><ChatIcon />Care assistant</h2>
          <p className="mt-1 text-sm text-stone-600">A space for questions about your care.</p>
        </div>
        <span className="rounded-lg bg-[var(--accent-surface)] px-3 py-1 text-xs font-medium text-[var(--accent-text)]">Preview · AI not connected</span>
      </header>
      <div className="space-y-4 p-4 sm:p-6">
        <p id="care-assistant-preview" className="text-sm leading-6 text-stone-600">Try the conversation layout. Messages stay on this page until you leave or reload; nothing is sent or saved. This is separate from messaging your therapist.</p>
        {messages.length === 0 && <div className="py-6 sm:py-10">
          <h3 className="text-xl font-semibold">What would you like to understand?</h3>
          <p className="mt-2 max-w-xl text-sm leading-6 text-stone-600">The assistant is being designed to explain information shared with you and help with practical questions about appointments and billing.</p>
          <div className="mt-5 flex flex-wrap gap-2">
            {["Help me understand a shared insight", "When is my next appointment?", "Help me understand my bill"].map(prompt => <button key={prompt} type="button" className={control} onClick={() => setDraft(prompt)}>{prompt}</button>)}
          </div>
        </div>}
        <div role="log" aria-label="Conversation preview" aria-live="polite" aria-relevant="additions" className="space-y-4">
          {messages.map((message, index) => <div key={index} className={`max-w-2xl rounded-xl border border-[var(--border)] p-4 ${message.role === "user" ? "ml-auto bg-[var(--accent-surface)]" : "bg-[var(--surface-subtle)]"}`}>
            <p className="mb-1 text-xs font-semibold text-stone-600">{message.role === "user" ? "You" : "Care assistant · preview"}</p>
            <p className="whitespace-pre-wrap break-words text-sm leading-6">{message.text}</p>
          </div>)}
        </div>
        <form onSubmit={submit} className="border-t border-[var(--border)] pt-4">
          <label htmlFor="care-assistant-message" className="text-sm font-medium">Your message</label>
          <textarea id="care-assistant-message" aria-describedby="care-assistant-preview" value={draft} onChange={event => setDraft(event.target.value)} maxLength={2000} rows={3} placeholder="Ask a question…" className="mt-2 block w-full resize-y rounded-xl border border-[var(--border)] bg-[var(--surface-subtle)] p-3 text-sm focus:border-[var(--accent-strong)] focus:outline-none" />
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-stone-600">Not monitored by your therapist. Not an emergency service.</p>
            <button type="submit" disabled={!draft.trim()} className="cursor-grab rounded-xl bg-[var(--accent-strong)] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[var(--accent-strong-hover)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-60">Send preview</button>
          </div>
        </form>
      </div>
    </div>
  </section>;
}
