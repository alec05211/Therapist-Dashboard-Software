type RecordingControlsProps = {
  isRecording: boolean;
  isBusy: boolean;
  onToggle: () => void;
};

export function RecordingControls({ isRecording, isBusy, onToggle }: RecordingControlsProps) {
  return (
    <button
      type="button"
      className={`grid size-32 place-items-center rounded-full text-lg font-bold text-white shadow-sm transition focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-emerald-700 disabled:cursor-wait disabled:opacity-70 ${isRecording ? "bg-stone-800 hover:bg-stone-700" : "bg-red-700 hover:bg-red-800"}`}
      aria-pressed={isRecording}
      disabled={isBusy}
      onClick={onToggle}
    >
      {isRecording ? "Stop" : "Record"}
    </button>
  );
}
