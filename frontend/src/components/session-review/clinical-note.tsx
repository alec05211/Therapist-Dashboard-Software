"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import type { JSONContent } from "@tiptap/core";
import { EditorContent, useEditor, useEditorState } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { CollapsibleContentPanel } from "@/components/collapsible-content-panel";
import { api } from "@/lib/api";
import type { ClinicalNoteSection, ClinicalNoteVersion, LongitudinalRecordContext } from "@/lib/types";

type SaveState = "loading" | "idle" | "unsaved" | "saving" | "saved" | "error" | "finalizing";

const control = "grid size-8 cursor-grab place-items-center rounded-lg border border-transparent text-stone-700 active:cursor-grabbing hover:border-stone-300 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-emerald-700 disabled:cursor-wait disabled:opacity-50";
const CLINICAL_NOTE_COLLAPSED_PREVIEW_HEIGHT = 136;
const noteDocumentClass = "pb-4 pl-14 pr-4 pt-3 text-sm leading-6 text-stone-900 [&_h2]:mb-1 [&_h2]:mt-4 [&_h2]:text-base [&_h2]:font-semibold [&_h3]:mb-1 [&_h3]:mt-3 [&_h3]:text-sm [&_h3]:font-semibold [&_p]:my-1 [&_ul]:my-1 [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:my-1 [&_ol]:list-decimal [&_ol]:pl-6 [&>:first-child]:mt-0";

function sectionsToDocument(sections: ClinicalNoteSection[]): JSONContent {
  return {
    type: "doc",
    content: sections.flatMap(section => [
      { type: "heading", attrs: { level: 2 }, content: [{ type: "text", text: section.name }] },
      { type: "bulletList", content: section.items.map(item => ({ type: "listItem", content: [{ type: "paragraph", content: item ? [{ type: "text", text: item }] : [] }] })) },
    ]),
  };
}

function FinalizeNoteDialog({ busy, onClose, onFinalize }: { busy: boolean; onClose: () => void; onFinalize: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [step, setStep] = useState<1 | 2>(1);
  useEffect(() => {
    if (!dialog.current?.open) dialog.current?.showModal();
  }, []);
  if (typeof document === "undefined") return null;
  return createPortal(
    <dialog ref={dialog} aria-labelledby={titleId} onCancel={event => { event.preventDefault(); if (!busy) onClose(); }} onClose={() => { if (!busy) onClose(); }} onClick={event => { if (event.target === event.currentTarget && !busy) onClose(); }} className="m-auto w-[min(92vw,480px)] rounded-2xl border border-stone-300 bg-white p-6 text-left text-stone-900 shadow-xl backdrop:bg-stone-950/50">
      <h2 id={titleId} className="text-lg font-semibold">{step === 1 ? "Finalize this clinical note?" : "Confirm finalization"}</h2>
      <p className="mt-3 text-sm leading-6 text-stone-600">{step === 1 ? "Review the note carefully before continuing. Finalization turns the current autosaved draft into the therapist-owned record for this session." : "This version will be locked and made available to the Insights synthesis pipeline. Later corrections will be saved as a separate amendment."}</p>
      <div className="mt-6 flex flex-wrap justify-end gap-2">
        <button type="button" disabled={busy} onClick={onClose} className="cursor-grab rounded-xl border border-stone-300 px-4 py-2 text-sm font-semibold text-stone-700 active:cursor-grabbing disabled:cursor-wait disabled:opacity-50">Cancel</button>
        {step === 1 ? <button type="button" onClick={() => setStep(2)} className="cursor-grab rounded-xl bg-emerald-800 px-4 py-2 text-sm font-semibold text-white active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Continue</button> : <button type="button" disabled={busy} onClick={onFinalize} className="cursor-grab rounded-xl bg-emerald-800 px-4 py-2 text-sm font-semibold text-white active:cursor-grabbing disabled:cursor-wait disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">{busy ? "Finalizing…" : "Finalize note"}</button>}
      </div>
    </dialog>,
    document.body,
  );
}

export function ClinicalNote({ sections, recordContext, sessionId, editable = false }: { sections: ClinicalNoteSection[]; recordContext?: LongitudinalRecordContext; sessionId?: string; editable?: boolean }) {
  const initialDocument = useRef(sectionsToDocument(sections));
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(editable);
  const editingRef = useRef(editable);
  const suppressEditorUpdate = useRef(false);
  const [note, setNote] = useState<ClinicalNoteVersion | null>(null);
  const noteRef = useRef<ClinicalNoteVersion | null>(null);
  const [saveState, setSaveState] = useState<SaveState>(editable ? "loading" : "idle");
  const [error, setError] = useState<string | null>(null);
  const [finalizeOpen, setFinalizeOpen] = useState(false);
  const [preview, setPreview] = useState(sections.flatMap(section => [section.name, ...section.items]).join(" · "));
  const pendingContent = useRef<ClinicalNoteVersion["content"] | null>(null);
  const lastPersistedDocument = useRef(JSON.stringify(initialDocument.current));
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveInFlight = useRef<Promise<void> | null>(null);
  const saveIndicatorTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [savedIndicatorVisible, setSavedIndicatorVisible] = useState(false);

  async function persistPending(): Promise<void> {
    if (!recordContext || !sessionId) return;
    if (saveInFlight.current) {
      await saveInFlight.current;
      if (pendingContent.current) await persistPending();
      return;
    }
    const content = pendingContent.current;
    if (!content) return;
    pendingContent.current = null;
    setSaveState("saving");
    const request = api.saveClinicalNoteDraft(recordContext.organizationId, recordContext.clientId, sessionId, content).then(saved => {
      const next: ClinicalNoteVersion = { ...saved, content };
      lastPersistedDocument.current = JSON.stringify(content.document);
      noteRef.current = next;
      setNote(next);
      setSaveState("saved");
      setSavedIndicatorVisible(true);
      if (saveIndicatorTimer.current) clearTimeout(saveIndicatorTimer.current);
      saveIndicatorTimer.current = setTimeout(() => setSavedIndicatorVisible(false), 1400);
    }).catch(reason => {
      pendingContent.current = content;
      setSaveState("error");
      setError(reason instanceof Error ? reason.message : "The clinical note could not be autosaved.");
      throw reason;
    }).finally(() => { saveInFlight.current = null; });
    saveInFlight.current = request;
    await request;
    if (pendingContent.current) await persistPending();
  }

  const editor = useEditor({
    extensions: [StarterKit.configure({ heading: { levels: [2, 3] } })],
    content: initialDocument.current,
    editable: false,
    immediatelyRender: false,
    editorProps: { attributes: { "aria-label": "Clinical note editor", class: `min-h-72 focus:outline-none ${noteDocumentClass}` } },
    onUpdate: ({ editor: currentEditor, transaction }) => {
      if (!transaction.docChanged || suppressEditorUpdate.current || !editingRef.current || !recordContext || !sessionId) return;
      const document = currentEditor.getJSON() as Record<string, unknown>;
      if (JSON.stringify(document) === lastPersistedDocument.current) {
        pendingContent.current = null;
        if (saveTimer.current) clearTimeout(saveTimer.current);
        setSaveState(noteRef.current ? "saved" : "idle");
        return;
      }
      const content: ClinicalNoteVersion["content"] = { schema_version: 1, editor: "tiptap", document, plain_text: currentEditor.getText({ blockSeparator: "\n" }) };
      pendingContent.current = content;
      setSavedIndicatorVisible(false);
      setPreview(content.plain_text.replaceAll("\n", " · "));
      setSaveState("unsaved");
      setError(null);
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => void persistPending(), 700);
    },
  });

  useEffect(() => {
    editingRef.current = editing;
    if (!editor) return;
    suppressEditorUpdate.current = true;
    editor.setEditable(editing);
    const frame = window.requestAnimationFrame(() => {
      suppressEditorUpdate.current = false;
    });
    return () => {
      window.cancelAnimationFrame(frame);
      suppressEditorUpdate.current = false;
    };
  }, [editing, editor]);

  useEffect(() => {
    if (!editable || !recordContext || !sessionId || !editor) return;
    let cancelled = false;
    void api.getLatestClinicalNoteVersion(recordContext.organizationId, recordContext.clientId, sessionId).then(({ note: latest }) => {
      if (cancelled) return;
      noteRef.current = latest;
      setNote(latest);
      setEditing(latest?.status !== "finalized");
      if (latest?.content?.document) {
        editor.commands.setContent(latest.content.document as JSONContent, { emitUpdate: false, errorOnInvalidContent: true });
        setPreview(latest.content.plain_text.replaceAll("\n", " · "));
      }
      lastPersistedDocument.current = JSON.stringify(editor.getJSON());
      setSaveState("idle");
    }).catch(reason => {
      if (cancelled) return;
      setSaveState("error");
      setError(reason instanceof Error ? reason.message : "Saved clinical-note versions could not be loaded.");
    });
    return () => { cancelled = true; };
  }, [editable, editor, recordContext, sessionId]);

  useEffect(() => () => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    if (saveIndicatorTimer.current) clearTimeout(saveIndicatorTimer.current);
    const content = pendingContent.current;
    if (content && recordContext && sessionId) void api.saveClinicalNoteDraft(recordContext.organizationId, recordContext.clientId, sessionId, content);
  }, [recordContext, sessionId]);

  const active = useEditorState({ editor, selector: ({ editor: currentEditor }) => ({ bold: currentEditor?.isActive("bold") ?? false, italic: currentEditor?.isActive("italic") ?? false, strike: currentEditor?.isActive("strike") ?? false, bullet: currentEditor?.isActive("bulletList") ?? false, ordered: currentEditor?.isActive("orderedList") ?? false, heading2: currentEditor?.isActive("heading", { level: 2 }) ?? false, heading3: currentEditor?.isActive("heading", { level: 3 }) ?? false }) });

  if (!sections.length || !editor) return null;
  const finalized = note?.status === "finalized";
  const summary = finalized
    ? <span className="font-medium text-emerald-800">FINALIZED</span>
    : <span className="font-medium italic tracking-wide text-amber-700">{note ? "DRAFT" : "AI DRAFT"}</span>;
  const saveIndicatorVisible = saveState === "unsaved" || saveState === "saving" || savedIndicatorVisible;
  const openFinalize = () => { setExpanded(true); setFinalizeOpen(true); };
  const finalize = async () => {
    if (!recordContext || !sessionId) return;
    setSaveState("finalizing");
    setError(null);
    try {
      if (saveTimer.current) clearTimeout(saveTimer.current);
      if (!noteRef.current || pendingContent.current) pendingContent.current = { schema_version: 1, editor: "tiptap", document: editor.getJSON() as Record<string, unknown>, plain_text: editor.getText({ blockSeparator: "\n" }) };
      await persistPending();
      const current = noteRef.current;
      if (!current) throw new Error("The clinical note must finish saving before it can be finalized.");
      const result = await api.finalizeClinicalNoteDraft(recordContext.organizationId, recordContext.clientId, sessionId, current.id);
      const finalizedNote: ClinicalNoteVersion = { ...current, ...result, status: "finalized" };
      noteRef.current = finalizedNote;
      setNote(finalizedNote);
      setEditing(false);
      setFinalizeOpen(false);
      setSaveState("idle");
    } catch (reason) {
      setSaveState("error");
      setError(reason instanceof Error ? reason.message : "The clinical note could not be finalized.");
    }
  };
  const formatButton = (label: string, pressed: boolean, action: () => void, content: ReactNode) => <button type="button" aria-label={label} aria-pressed={pressed} onClick={action} className={`${control} ${pressed ? "border-stone-400 bg-stone-200 text-stone-900" : ""}`}>{content}</button>;
  const formatControls = <div role="toolbar" aria-label="Clinical note formatting" className="flex items-center gap-1 whitespace-nowrap">
    <select aria-label="Text style" value={active?.heading2 ? "2" : active?.heading3 ? "3" : "0"} onChange={event => { const level = Number(event.target.value); if (level === 0) editor.chain().focus().setParagraph().run(); else editor.chain().focus().toggleHeading({ level: level as 2 | 3 }).run(); }} className="mr-1 cursor-grab rounded-lg border border-stone-300 bg-white px-2 py-1.5 text-xs text-stone-800 active:cursor-grabbing focus:outline-none focus-visible:border-stone-500"><option value="0">Paragraph</option><option value="2">Heading</option><option value="3">Subheading</option></select>
    {formatButton("Bold", Boolean(active?.bold), () => editor.chain().focus().toggleBold().run(), <strong>B</strong>)}
    {formatButton("Italic", Boolean(active?.italic), () => editor.chain().focus().toggleItalic().run(), <em>I</em>)}
    {formatButton("Strikethrough", Boolean(active?.strike), () => editor.chain().focus().toggleStrike().run(), <span className="line-through">S</span>)}
    <span className="mx-1 h-5 w-px shrink-0 bg-stone-300" aria-hidden="true" />
    {formatButton("Bulleted list", Boolean(active?.bullet), () => editor.chain().focus().toggleBulletList().run(), <span aria-hidden="true">•≡</span>)}
    {formatButton("Numbered list", Boolean(active?.ordered), () => editor.chain().focus().toggleOrderedList().run(), <span aria-hidden="true">1≡</span>)}
    <span className="mx-1 h-5 w-px shrink-0 bg-stone-300" aria-hidden="true" />
    {formatButton("Undo", false, () => editor.chain().focus().undo().run(), <span aria-hidden="true">↶</span>)}
    {formatButton("Redo", false, () => editor.chain().focus().redo().run(), <span aria-hidden="true">↷</span>)}
  </div>;
  const noteActions = editing ? <>
    {saveIndicatorVisible && <span role="status" aria-live="polite" className={`min-w-14 text-right text-xs font-medium ${saveState === "saved" ? "text-emerald-800" : "text-stone-600"}`}>{saveState === "saved" ? "Saved" : <>Saving<span aria-hidden="true" className="processing-ellipsis inline-block w-4 text-left"><span>.</span><span>.</span><span>.</span></span></>}</span>}
    <button type="button" disabled={finalized || saveState === "loading" || saveState === "saving" || saveState === "finalizing"} onClick={openFinalize} aria-label="Finalize clinical note" title={finalized ? "Save an amendment before finalizing" : "Finalize note"} className={`${control} ml-1 border-stone-300 bg-stone-50`}><svg viewBox="0 0 20 20" className="size-4" fill="none" aria-hidden="true"><path d="m4 10.5 3.5 3.5L16 5.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg></button>
  </> : <button type="button" disabled={saveState === "loading" || saveState === "finalizing"} onClick={() => setEditing(true)} aria-label="Amend clinical note" title="Amend note" className={`${control} border-stone-300 bg-stone-50`}><svg viewBox="0 0 20 20" className="size-4" fill="none" aria-hidden="true"><path d="m4 14.8.5-3.2L12.8 3.3a1.8 1.8 0 0 1 2.5 0l1.4 1.4a1.8 1.8 0 0 1 0 2.5l-8.3 8.3-3.2.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /><path d="m11.5 4.6 3.9 3.9" stroke="currentColor" strokeWidth="1.5" /></svg></button>;

  return <>
    <CollapsibleContentPanel title="Clinical Note" summary={summary} ariaLabel={finalized ? "Finalized clinical note" : "Draft clinical note"} preview={preview || "No note details available."} previewContent={<div className="border-t border-stone-200 bg-white"><div className={noteDocumentClass} dangerouslySetInnerHTML={{ __html: editor.getHTML() }} /></div>} collapsedPreviewHeight={CLINICAL_NOTE_COLLAPSED_PREVIEW_HEIGHT} expanded={expanded} onExpandedChange={setExpanded} keepMounted className="mt-5" headerCenter={editable && expanded && editing && saveState !== "loading" ? formatControls : undefined} headerActions={editable && expanded && saveState !== "loading" ? noteActions : undefined}>
      <div className="border-t border-stone-200 bg-white">
        <div onBlur={() => { if (editingRef.current && pendingContent.current) void persistPending(); }}><EditorContent editor={editor} /></div>
        {error && <p role="alert" className="border-t border-stone-200 px-5 py-3 text-xs text-red-700">{error}</p>}
      </div>
    </CollapsibleContentPanel>
    {finalizeOpen && <FinalizeNoteDialog busy={saveState === "finalizing"} onClose={() => setFinalizeOpen(false)} onFinalize={() => void finalize()} />}
  </>;
}
