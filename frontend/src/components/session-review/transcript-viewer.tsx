import { useEffect, useRef, useState, type SyntheticEvent } from "react";
import { ClinicalNote } from "@/components/session-review/clinical-note";
import type { Transcript } from "@/lib/types";

type Props = {
  transcript: Transcript | null;
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

export function TranscriptViewer({ transcript, readOnly = false, showTranscript = true, showClinicalNote = true, activeSegment: controlledSegment, isPlaying: controlledPlaying, onPlaySegment, onAudioTimeUpdate, onAudioPlay, onAudioPause, onAudioEnded }: Props) {
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
    setExpanded(true);
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
      {showTranscript && <section className="relative mt-5 overflow-hidden rounded-xl border border-stone-200 bg-stone-100 text-stone-900 transition duration-200 ease-out hover:bg-stone-200" aria-label="Transcript">
        {!expanded ? (
          <button type="button" className="block w-full cursor-grab p-4 text-left active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-stone-700" aria-expanded="false" onClick={() => setExpanded(true)}>
            <span className="flex items-baseline gap-2"><span className="text-base font-semibold">Transcript</span><span className="text-sm text-stone-600">{summary}</span></span>
            <span className="collapsed-content-preview mt-3 block max-h-24 overflow-hidden text-sm leading-6 text-stone-600">{preview || "No transcript details available."}</span>
            <span className="absolute bottom-3 right-4 text-lg text-stone-600" aria-hidden="true">⌄</span>
          </button>
        ) : <>
          <button type="button" className="w-full cursor-grab p-4 pr-12 text-left active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-stone-700" aria-expanded="true" onClick={() => setExpanded(false)}>
            <span className="flex items-baseline gap-2"><span className="text-base font-semibold">Transcript</span><span className="text-sm text-stone-600">{summary}</span></span>
            <span className="absolute right-4 top-3 text-lg text-stone-600" aria-hidden="true">⌃</span>
          </button>
          <ol className="grid list-none gap-2 px-4 pb-4 pt-1">
            {transcript.segments.map((segment, index) => {
              const active = activeSegment === index;
              const className = `group w-full cursor-grab rounded-lg border p-2 text-left text-sm transition duration-200 ease-out active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-emerald-700 ${active ? "border-emerald-300 bg-emerald-50" : "border-transparent hover:border-stone-200 hover:bg-stone-200/70"}`;
              if (readOnly || !transcript.recording_url) return <li key={index} className="rounded-lg p-2 text-sm leading-6">{segment.speaker && <span className="mr-2 rounded-full bg-stone-200 px-2 py-0.5 text-xs font-bold text-stone-700">{transcript.speakers[segment.speaker] || segment.speaker}</span>}{segment.text.trim()}</li>;
              return <li key={`${segment.start}-${index}`} ref={active ? activeSegmentElement : undefined}><button type="button" className={className} aria-label={`${active && isPlaying ? "Pause" : "Play"} segment at ${formatTime(segment.start)}`} onClick={() => playSegment(index)}><span className={`mr-2 inline-block w-5 text-emerald-800 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 ${active ? "opacity-100" : ""}`} aria-hidden="true">{active && isPlaying ? "❚❚" : "▶"}</span><time className="mr-2 text-stone-500">[{formatTime(segment.start)}]</time>{segment.speaker ? <span className="mr-2 rounded-full bg-stone-200 px-2 py-0.5 text-xs font-bold text-stone-700">{transcript.speakers[segment.speaker] || segment.speaker}</span> : null}{segment.text.trim()}</button></li>;
            })}
          </ol>
          {!readOnly && transcript.recording_url ? <div className="border-t border-stone-200 bg-stone-50 px-4 py-3"><div className="flex flex-wrap items-center gap-3"><button type="button" onClick={togglePlayback} className="grid size-9 shrink-0 cursor-grab place-items-center rounded-full bg-emerald-800 text-sm text-white active:cursor-grabbing hover:bg-emerald-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700" aria-label={isPlaying ? "Pause recording" : "Play recording"}>{isPlaying ? "❚❚" : "▶"}</button><span className="w-10 shrink-0 text-xs tabular-nums text-stone-600">{formatTime(currentTime)}</span><input type="range" min="0" max={duration || 0} step="0.1" value={Math.min(currentTime, duration || 0)} onChange={(event) => seek(event.target.value)} className="h-1 min-w-24 flex-1 cursor-grab accent-emerald-800 active:cursor-grabbing" aria-label="Recording position" /><span className="w-10 shrink-0 text-right text-xs tabular-nums text-stone-600">{formatTime(duration)}</span><label className="flex items-center gap-1.5 text-xs text-stone-600"><span aria-hidden="true">◖</span><span className="sr-only">Volume</span><input type="range" min="0" max="1" step="0.05" value={volume} onChange={(event) => changeVolume(event.target.value)} className="h-1 w-16 cursor-grab accent-emerald-800 active:cursor-grabbing" aria-label="Volume" /></label><a href={transcript.recording_url} download className="cursor-grab rounded-md px-2 py-1 text-xs font-semibold text-emerald-800 underline underline-offset-2 hover:bg-emerald-50 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700">Download</a></div></div> : null}
        </>}
      </section>}
      {!readOnly && transcript.recording_url ? <audio ref={audio} className="sr-only" src={transcript.recording_url} onLoadedMetadata={(event) => setDuration(event.currentTarget.duration)} onTimeUpdate={(event) => { setCurrentTime(event.currentTarget.currentTime); setPlayingSegment(transcript.segments.findIndex(segment => event.currentTarget.currentTime >= segment.start && event.currentTarget.currentTime < segment.end)); onAudioTimeUpdate?.(event); }} onPlay={() => { setPlaying(true); onAudioPlay?.(); }} onPause={() => { setPlaying(false); onAudioPause?.(); }} onEnded={() => { setPlaying(false); setPlayingSegment(-1); onAudioEnded?.(); }} onError={() => setPlaybackError("Recording unavailable or sharing access has changed.")} /> : null}
    </section>
  );
}
