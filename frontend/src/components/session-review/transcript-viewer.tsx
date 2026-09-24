import { useEffect, useRef, useState, type SyntheticEvent } from "react";
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
      activeSegmentElement.current?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
        block: "center",
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [activeSegment, expanded]);

  const summary = transcript ? (transcript.segments.length ? `${transcript.segments.length} ${readOnly ? "segments" : "timestamped segments"}` : "No speech detected") : "";
  const preview = transcript?.segments.slice(0, 5).map((segment) => segment.text.trim()).join(" ") || "";
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

  return (
    <section className="w-full rounded-2xl border border-stone-200 bg-white p-5 shadow-sm" aria-label="Associated materials">
      {playbackError && <p role="alert" className="mb-3 text-sm text-red-700">{playbackError}</p>}
      <h3 className="text-base font-semibold text-stone-900">Associated materials</h3>
      {showClinicalNote && <ClinicalNote sections={transcript.clinical_note} />}
      {showTranscript && <CollapsibleContentPanel title="Transcript" summary={summary} preview={preview || "No transcript details available."} expanded={expanded} onExpandedChange={setExpanded} className="mt-5">
          <ol className="grid list-none gap-2 px-4 pb-4 pt-1">
            {transcript.segments.map((segment, index) => {
              const active = activeSegment === index;
              const proposals = readOnly ? [] : quotes.entries.filter(entry => entry.evidence.some(source => source.session_id === sessionId && source.segment_index === index && source.quote?.trim() === segment.text.trim()));
              if (proposals.length && recordContext) return <li key={`${segment.start}-${index}`} ref={active ? activeSegmentElement : undefined} className={`rounded-xl border p-3 text-sm leading-7 ${active ? "border-emerald-300 bg-emerald-50" : "border-stone-300 bg-stone-50"}`}>
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  {transcript.recording_url && <button type="button" onClick={() => playSegment(index)} aria-label={`${active && isPlaying ? "Pause" : "Play"} segment at ${formatTime(segment.start)}`} className="cursor-grab rounded-lg px-2 text-emerald-800 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-emerald-700">{active && isPlaying ? "❚❚" : "▶"}</button>}
                  <time className="text-xs text-stone-500">{formatTime(segment.start)}</time>
                  {segment.speaker && <span className="text-xs font-semibold text-stone-700">{transcript.speakers[segment.speaker] || segment.speaker}</span>}
                  <span className="text-xs text-stone-600">{proposals.some(entry => entry.status === "proposed") ? "Suggested passage" : "Saved passage"}</span>
                </div>
                <button type="button" aria-expanded={selectedQuoteSegment === index} onClick={() => setSelectedQuoteSegment(selectedQuoteSegment === index ? null : index)} className="w-full cursor-grab text-left text-stone-800 underline decoration-stone-400 decoration-2 underline-offset-4 active:cursor-grabbing focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-emerald-700">{segment.text.trim()}</button>
                {selectedQuoteSegment === index && proposals.map(entry => <QuoteReview key={entry.id} entry={entry} recordContext={recordContext} onSaved={quotes.onSaved} />)}
              </li>;
              const className = `group w-full cursor-grab rounded-lg border p-2 text-left text-sm transition duration-200 ease-out active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-emerald-700 ${active ? "border-emerald-300 bg-emerald-50" : "border-transparent hover:border-stone-200 hover:bg-stone-200/70"}`;
              if (readOnly || !transcript.recording_url) return <li key={index} className="rounded-lg p-2 text-sm leading-6">{segment.speaker && <span className="mr-2 rounded-full bg-stone-200 px-2 py-0.5 text-xs font-bold text-stone-700">{transcript.speakers[segment.speaker] || segment.speaker}</span>}{segment.text.trim()}</li>;
              return <li key={`${segment.start}-${index}`} ref={active ? activeSegmentElement : undefined}><button type="button" className={className} aria-label={`${active && isPlaying ? "Pause" : "Play"} segment at ${formatTime(segment.start)}`} onClick={() => playSegment(index)}><span className={`mr-2 inline-block w-5 text-emerald-800 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 ${active ? "opacity-100" : ""}`} aria-hidden="true">{active && isPlaying ? "❚❚" : "▶"}</span><time className="mr-2 text-stone-500">[{formatTime(segment.start)}]</time>{segment.speaker ? <span className="mr-2 rounded-full bg-stone-200 px-2 py-0.5 text-xs font-bold text-stone-700">{transcript.speakers[segment.speaker] || segment.speaker}</span> : null}{segment.text.trim()}</button></li>;
            })}
          </ol>
          {quotes.error && <p role="alert" className="px-4 pb-4 text-sm text-red-700">Suggested passages unavailable: {quotes.error}</p>}
          {!readOnly && transcript.recording_url ? <div className="border-t border-stone-200 bg-stone-50 px-4 py-3"><div className="flex flex-wrap items-center gap-3"><button type="button" onClick={togglePlayback} className="grid size-9 shrink-0 cursor-grab place-items-center rounded-full bg-emerald-800 text-sm text-white active:cursor-grabbing hover:bg-emerald-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700" aria-label={isPlaying ? "Pause recording" : "Play recording"}>{isPlaying ? "❚❚" : "▶"}</button><span className="w-10 shrink-0 text-xs tabular-nums text-stone-600">{formatTime(currentTime)}</span><input type="range" min="0" max={duration || 0} step="0.1" value={Math.min(currentTime, duration || 0)} onChange={(event) => seek(event.target.value)} className="h-1 min-w-24 flex-1 cursor-grab accent-emerald-800 active:cursor-grabbing" aria-label="Recording position" /><span className="w-10 shrink-0 text-right text-xs tabular-nums text-stone-600">{formatTime(duration)}</span><label className="flex items-center gap-1.5 text-xs text-stone-600"><span aria-hidden="true">◖</span><span className="sr-only">Volume</span><input type="range" min="0" max="1" step="0.05" value={volume} onChange={(event) => changeVolume(event.target.value)} className="h-1 w-16 cursor-grab accent-emerald-800 active:cursor-grabbing" aria-label="Volume" /></label><a href={transcript.recording_url} download className="cursor-grab rounded-md px-2 py-1 text-xs font-semibold text-emerald-800 underline underline-offset-2 hover:bg-emerald-50 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Download</a></div></div> : null}
      </CollapsibleContentPanel>}
      {!readOnly && transcript.recording_url ? <audio ref={audio} className="sr-only" src={transcript.recording_url} onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)} onTimeUpdate={(event) => { setCurrentTime(event.currentTarget.currentTime); setPlayingSegment(transcript.segments.findIndex(segment => event.currentTarget.currentTime >= segment.start && event.currentTarget.currentTime < segment.end)); onAudioTimeUpdate?.(event); }} onPlay={() => { setPlaying(true); onAudioPlay?.(); }} onPause={() => { setPlaying(false); onAudioPause?.(); }} onEnded={() => { setPlaying(false); setPlayingSegment(-1); onAudioEnded?.(); }} onError={() => setPlaybackError("Recording unavailable or sharing access has changed.")} /> : null}
    </section>
  );
}
