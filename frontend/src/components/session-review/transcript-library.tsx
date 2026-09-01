import type { TranscriptListItem } from "@/lib/types";

type TranscriptLibraryProps = {
  transcripts: TranscriptListItem[];
  activeId: string | null;
  error: string | null;
  onOpen: (id: string) => void;
};

export function TranscriptLibrary({ transcripts, activeId, error, onOpen }: TranscriptLibraryProps) {
  return (
    <aside className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-stone-200" aria-label="Saved transcripts">
      <h2 className="text-lg font-semibold">Saved transcripts</h2>
      {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      {!error && transcripts.length === 0 ? <p className="mt-3 text-sm text-stone-500">No saved transcripts yet.</p> : null}
      <div className="mt-4 grid max-h-[32.5rem] gap-2 overflow-y-auto">
        {transcripts.map((transcript) => (
          <button
            key={transcript.id}
            type="button"
            onClick={() => onOpen(transcript.id)}
            className={`rounded-xl border p-3 text-left text-sm transition hover:border-stone-500 focus-visible:outline-2 focus-visible:outline-emerald-700 ${activeId === transcript.id ? "border-stone-900 bg-stone-100" : "border-stone-200 bg-white"}`}
          >
            <strong className="block truncate">{transcript.label}</strong>
            <span className="mt-1 block text-xs text-stone-500">
              {transcript.created_at ? new Date(transcript.created_at).toLocaleString() : "Date unavailable"}
            </span>
          </button>
        ))}
      </div>
    </aside>
  );
}
