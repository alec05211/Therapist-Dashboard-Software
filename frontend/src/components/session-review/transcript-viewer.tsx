import { useEffect, useId, useRef, useState, type SyntheticEvent } from "react";
import { CollapsibleContentPanel } from "@/components/collapsible-content-panel";
import { ClinicalNote } from "@/components/session-review/clinical-note";
import type { LongitudinalRecordContext, Transcript } from "@/lib/types";
import { QuoteReview, useQuoteProposals } from "@/components/session-review/quote-review";

type Props = {
  transcript: Transcript | null;
  recordContext?: LongitudinalRecordContext;
  sessionId?: string;
  readOnly?: boolean;
  showTranscript?: boolean;
  showClinicalNote?: boolean;
  activeSegment?: number;
  isPlaying?: boolean;
  onPlaySegment?: (index: number) => void;
  onAudioTimeUpdate?: (event: SyntheticEvent<HTMLAudioElement>) => void;
  onAudioPlay?: () => void;
  onAudioPause?: () => void;
  onAudioEnded?: () => void;
};

const formatTime = (seconds: number) => {
  const safe = Number.isFinite(seconds) ? seconds : 0;
  return `${Math.floor(safe / 60)}:${Math.floor(safe % 60).toString().padStart(2, "0")}`;
};

export function TranscriptViewer({ transcript, recordContext, sessionId, readOnly = false, showTranscript = true, showClinicalNote = true, activeSegment: controlledSegment, isPlaying: controlledPlaying, onPlaySegment, onAudioTimeUpdate, onAudioPlay, onAudioPause, onAudioEnded }: Props) {
  const transcriptId = useId();
  const quotes = useQuoteProposals(readOnly ? undefined : recordContext, sessionId);
  const [selectedQuoteSegment, setSelectedQuoteSegment] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [playingSegment, setPlayingSegment] = useState(-1);
  const [playbackError, setPlaybackError] = useState<string | null>(null);
  const activeSegment = controlledSegment ?? playingSegment;
  const isPlaying = controlledPlaying ?? playing;
  const [expanded, setExpanded] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const audio = useRef<HTMLAudioElement>(null);
  const activeSegmentElement = useRef<HTMLLIElement>(null);

  useEffect(() => {
    if (activeSegment < 0) return;
    const frame = window.requestAnimationFrame(() => setExpanded(true));
    return () => window.cancelAnimationFrame(frame);
  }, [activeSegment]);

  useEffect(() => {
    if (activeSegment < 0 || !expanded) return;
    const frame = window.requestAnimationFrame(() => {
      const element = activeSegmentElement.current;
      if (!element) return;
      const bounds = element.getBoundingClientRect();
      if (bounds.bottom > 0 && bounds.top < window.innerHeight) return;
      element.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "nearest",
        inline: "nearest",
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [activeSegment, expanded]);

  const summary = transcript ? (transcript.segments.length ? `${transcript.segments.length} ${readOnly ? "segments" : "timestamped segments"}` : "No speech detected") : "";
  const playSegment = (index: number) => {
    if (onPlaySegment) { onPlaySegment(index); return; }
    const player = audio.current;
    if (!player) return;
    setPlaybackError(null);
    if (activeSegment === index && !player.paused) { player.pause(); return; }
    player.currentTime = transcript?.segments[index].start ?? 0;
    setPlayingSegment(index);
    void player.play().catch(() => setPlaybackError("Audio playback could not start. Please try again."));
  };
  const togglePlayback = () => {
    if (!audio.current) return;
    if (audio.current.paused) void audio.current.play().catch(() => setPlaybackError("Audio playback could not start. Please try again."));
    else audio.current.pause();
  };
  const seek = (value: string) => {
    if (!audio.current) return;
    const time = Number(value);
    audio.current.currentTime = time;
    setCurrentTime(time);
  };
  const changeVolume = (value: string) => {
    if (!audio.current) return;
    const next = Number(value);
    audio.current.volume = next;
    setVolume(next);
  };

  if (!transcript) return <section className="w-full rounded-2xl border border-stone-200 bg-white p-5 shadow-sm" aria-label="Associated materials"><p className="text-sm text-stone-500">Choose a completed session to review its associated materials.</p></section>;

  const previewOnly = !expanded;
  const transcriptRows = (
    <ol className="list-none px-4 pb-4 pt-1">
            {(previewOnly ? transcript.segments.slice(0, 5) : transcript.segments).map((segment, index) => {
              const active = activeSegment === index;
              const proposals = readOnly ? [] : quotes.entries.filter(entry => entry.evidence.some(source => source.session_id === sessionId && source.segment_index === index && source.quote?.trim() === segment.text.trim()));
              const flagged = proposals.length > 0 && Boolean(recordContext);
              const reviewOpen = !previewOnly && flagged && selectedQuoteSegment === index;
              const reviewId = `${transcriptId}-review-${index}`;
              const canPlay = !readOnly && Boolean(transcript.recording_url);
              const speaker = segment.speaker ? transcript.speakers[segment.speaker] || segment.speaker : null;
              return <li key={`${segment.start}-${index}`} ref={active && !previewOnly ? activeSegmentElement : undefined} className={`group/segment grid grid-cols-[minmax(0,max-content)_minmax(0,1fr)] items-start gap-x-3 rounded-md px-1 py-1 text-sm leading-6 ${active ? "bg-emerald-50" : ""}`}>
                {canPlay ? <button type="button" onClick={() => playSegment(index)} aria-label={`${active && isPlaying ? "Pause" : "Play"} segment at ${formatTime(segment.start)}`} title={`${active && isPlaying ? "Pause" : "Play"} from ${formatTime(segment.start)}`} className={`inline-flex min-h-8 max-w-[45vw] cursor-grab items-baseline gap-2 rounded-lg border px-2 py-[3px] text-sm font-semibold tabular-nums text-stone-700 transition duration-200 ease-out group-hover/segment:border-[var(--border)] group-hover/segment:bg-[var(--surface)] group-hover/segment:shadow-sm group-focus-within/segment:border-[var(--border)] group-focus-within/segment:bg-[var(--surface)] hover:text-emerald-800 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${active ? "border-emerald-300 bg-white shadow-sm" : "border-transparent"}`}><svg viewBox="0 0 16 16" fill="currentColor" className={`size-4 shrink-0 self-center text-emerald-800 group-hover/segment:opacity-100 group-focus-within/segment:opacity-100 ${active ? "opacity-100" : "opacity-0"}`} aria-hidden="true">{active && isPlaying ? <><rect x="3" y="2" width="4" height="12" rx="1" /><rect x="9" y="2" width="4" height="12" rx="1" /></> : <path d="M3 2a.75.75 0 0 1 1.14-.64l9 5.25a1.6 1.6 0 0 1 0 2.78l-9 5.25A.75.75 0 0 1 3 14Z" />}</svg><time className="shrink-0">{formatTime(segment.start)}</time>{speaker && <span className="min-w-0 break-words text-left text-xs leading-6 font-normal text-stone-600">{speaker}:</span>}</button> : <div className="flex items-baseline gap-2 px-2 py-1"><time className="text-sm font-semibold tabular-nums text-stone-600">{formatTime(segment.start)}</time>{speaker && <span className="text-xs text-stone-600">{speaker}:</span>}</div>}
                <div className="min-w-0 break-words pt-1 text-stone-800">
                  {flagged ? <button type="button" aria-expanded={reviewOpen} aria-controls={reviewId} title="Flagged passage — select to review guidance" onClick={() => setSelectedQuoteSegment(reviewOpen ? null : index)} className="inline cursor-grab rounded-sm text-left font-bold text-stone-800 transition-colors hover:text-emerald-800 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700"><span className="sr-only">Review flagged passage: </span>{segment.text.trim()}</button> : <span>{segment.text.trim()}</span>}
                </div>
                {flagged && !previewOnly && <div id={reviewId} hidden={!reviewOpen} className="col-start-2 min-w-0">{reviewOpen && recordContext && proposals.map(entry => <QuoteReview key={entry.id} entry={entry} recordContext={recordContext} onSaved={quotes.onSaved} />)}</div>}
              </li>;
            })}
          </ol>
  );

  return (
    <section className="w-full rounded-2xl border border-stone-200 bg-white p-5 shadow-sm" aria-label="Associated materials">
      {playbackError && <p role="alert" className="mb-3 text-sm text-red-700">{playbackError}</p>}
      <h3 className="text-base font-semibold text-stone-900">Associated materials</h3>
      {showClinicalNote && <ClinicalNote sections={transcript.clinical_note} />}
      {showTranscript && <CollapsibleContentPanel title="Transcript" summary={summary} preview="No transcript details available." previewContent={transcript.segments.length ? transcriptRows : undefined} expanded={expanded} onExpandedChange={setExpanded} className="mt-5">
          {transcriptRows}
          {quotes.error && <p role="alert" className="px-4 pb-4 text-sm text-red-700">Suggested passages unavailable: {quotes.error}</p>}
          {!readOnly && transcript.recording_url ? <div className="border-t border-stone-200 bg-stone-50 px-4 py-3"><div className="flex flex-wrap items-center gap-3"><button type="button" onClick={togglePlayback} className="grid size-9 shrink-0 cursor-grab place-items-center rounded-full bg-emerald-800 text-sm text-white active:cursor-grabbing hover:bg-emerald-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700" aria-label={isPlaying ? "Pause recording" : "Play recording"}>{isPlaying ? "❚❚" : "▶"}</button><span className="w-10 shrink-0 text-xs tabular-nums text-stone-600">{formatTime(currentTime)}</span><input type="range" min="0" max={duration || 0} step="0.1" value={Math.min(currentTime, duration || 0)} onChange={(event) => seek(event.target.value)} className="h-1 min-w-24 flex-1 cursor-grab accent-emerald-800 active:cursor-grabbing" aria-label="Recording position" /><span className="w-10 shrink-0 text-right text-xs tabular-nums text-stone-600">{formatTime(duration)}</span><label className="flex items-center gap-1.5 text-xs text-stone-600"><span aria-hidden="true">◖</span><span className="sr-only">Volume</span><input type="range" min="0" max="1" step="0.05" value={volume} onChange={(event) => changeVolume(event.target.value)} className="h-1 w-16 cursor-grab accent-emerald-800 active:cursor-grabbing" aria-label="Volume" /></label><a href={transcript.recording_url} download className="cursor-grab rounded-md px-2 py-1 text-xs font-semibold text-emerald-800 underline underline-offset-2 hover:bg-emerald-50 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Download</a></div></div> : null}
      </CollapsibleContentPanel>}
      {!readOnly && transcript.recording_url ? <audio ref={audio} className="sr-only" src={transcript.recording_url} onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)} onTimeUpdate={(event) => { setCurrentTime(event.currentTarget.currentTime); setPlayingSegment(transcript.segments.findIndex(segment => event.currentTarget.currentTime >= segment.start && event.currentTarget.currentTime < segment.end)); onAudioTimeUpdate?.(event); }} onPlay={() => { setPlaying(true); onAudioPlay?.(); }} onPause={() => { setPlaying(false); onAudioPause?.(); }} onEnded={() => { setPlaying(false); setPlayingSegment(-1); onAudioEnded?.(); }} onError={() => setPlaybackError("Recording unavailable or sharing access has changed.")} /> : null}
    </section>
  );
}
