import { RecordingControls } from "@/components/session-review/recording-controls";

type ScheduledSessionLayoutProps = {
  isRecording: boolean;
  isBusy: boolean;
  onToggleRecording: () => void;
};

export function ScheduledSessionLayout({ isRecording, isBusy, onToggleRecording }: ScheduledSessionLayoutProps) {
  return (
    <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-stone-200" aria-label="Scheduled session preparation">
      <p className="text-sm font-medium text-emerald-800">Scheduled session</p>
      <h2 className="mt-1 text-lg font-semibold text-stone-900">Prepare for this session</h2>
      <p className="mt-2 text-sm leading-6 text-stone-600">Session preparation tools will appear here as they are introduced.</p>
      <div className="mt-5 border-t border-stone-200 pt-5">
        <RecordingControls isRecording={isRecording} isBusy={isBusy} onToggle={onToggleRecording} />
      </div>
    </section>
  );
}
