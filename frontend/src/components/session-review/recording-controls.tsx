type RecordingControlsProps = {
  isRecording: boolean;
  isBusy: boolean;
  onToggle: () => void;
};

export function RecordingControls({ isRecording, isBusy, onToggle }: RecordingControlsProps) {
  return (
    <div className="h-full" aria-label="Record a new session">
      <button
        type="button"
        className="flex h-full w-full cursor-grab items-center justify-center gap-2 bg-stone-100 px-4 py-3 text-sm font-semibold text-stone-900 transition-colors duration-200 hover:bg-stone-200 focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-emerald-700 active:cursor-grabbing disabled:cursor-wait disabled:opacity-60"
        aria-pressed={isRecording}
        disabled={isBusy}
        onClick={onToggle}
      >
        <span aria-hidden="true" className={`size-2.5 shrink-0 rounded-full bg-red-600 ${isRecording ? "animate-pulse motion-reduce:animate-none" : ""}`} />
        {isRecording ? "Stop Recording" : "Record Session"}
      </button>
    </div>
  );
}
