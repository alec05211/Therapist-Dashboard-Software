type RecordingControlsProps = {
  isRecording: boolean;
  isBusy: boolean;
  onToggle: () => void;
};

export function RecordingControls({ isRecording, isBusy, onToggle }: RecordingControlsProps) {
  return (
    <div aria-label="Record a new session">
      <button
        type="button"
        className={`w-full cursor-grab rounded-xl px-4 py-3 text-sm font-semibold text-white shadow-sm transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing disabled:cursor-wait disabled:opacity-70 ${isRecording ? "bg-red-700 hover:bg-red-800" : "bg-emerald-800 hover:bg-emerald-900"}`}
        aria-pressed={isRecording}
        disabled={isBusy}
        onClick={onToggle}
      >
        {isRecording ? "Stop recording" : "Record new session"}
      </button>
    </div>
  );
}
