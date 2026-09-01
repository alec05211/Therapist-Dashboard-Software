type SpeakerLabelEditorProps = {
  speakerIds: string[];
  labels: Record<string, string>;
  onChange: (speaker: string, value: string) => void;
  onSave: () => void;
  isSaving: boolean;
};

export function SpeakerLabelEditor({ speakerIds, labels, onChange, onSave, isSaving }: SpeakerLabelEditorProps) {
  if (!speakerIds.length) return null;
  return (
    <section className="mt-6 border-t border-stone-200 pt-5">
      <h3 className="font-semibold">Speaker names</h3>
      <div className="mt-3 grid gap-3">
        {speakerIds.map((speaker) => <label key={speaker} className="grid grid-cols-2 items-center gap-3 text-sm"><span>{speaker}</span><input className="rounded-md border border-stone-300 px-2 py-1.5" value={labels[speaker] || speaker} aria-label={`Name for ${speaker}`} onChange={(event) => onChange(speaker, event.target.value)} /></label>)}
      </div>
      <button type="button" className="mt-4 rounded-lg bg-stone-900 px-3 py-2 text-sm font-semibold text-white hover:bg-stone-700 disabled:opacity-60" disabled={isSaving} onClick={onSave}>{isSaving ? "Saving…" : "Save names"}</button>
    </section>
  );
}
