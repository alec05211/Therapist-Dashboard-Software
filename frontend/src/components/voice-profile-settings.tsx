"use client";

import { useEffect, useRef, useState } from "react";

type Profile = { available: boolean; enrolled: boolean; playable: boolean };
const prompt = "Today I am taking a moment to record my voice. The morning was quiet, and a gentle breeze moved through the trees. I picked up a blue notebook, opened the window, and thought about the week ahead. Some days are busy, while others leave more room to pause. I am speaking naturally, at a comfortable pace, just as I would in an ordinary conversation.";
const button = "cursor-grab px-3 py-2 text-sm transition-colors hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-emerald-700 active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-50";

function PlayIcon({ playing }: { playing: boolean }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="currentColor" className="size-4">{playing ? <path d="M6 4h4v16H6zm8 0h4v16h-4z" /> : <path d="m7 4 14 8-14 8z" />}</svg>;
}

export function VoiceProfileSettings() {
  const [profile, setProfile] = useState<Profile>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [preview, setPreview] = useState("");
  const [playing, setPlaying] = useState(false);
  const [audioVersion, setAudioVersion] = useState(0);
  const [openDialog, setOpenDialog] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const audio = useRef<HTMLAudioElement>(null);
  const recordingBlob = useRef<Blob | null>(null);
  const pending = useRef(false);

  useEffect(() => {
    let active = true;
    void fetch("/api/account/voice-profile").then(async response => {
      if (!response.ok) throw new Error();
      if (active) setProfile(await response.json());
    }).catch(() => { if (active) setError("Voice identity could not be loaded."); });
    return () => {
      active = false;
      if (recorder.current?.state === "recording") recorder.current.stop();
      stream.current?.getTracks().forEach(track => track.stop());
    };
  }, []);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  useEffect(() => {
    if (!recording) return;
    const timer = window.setInterval(() => setSeconds(value => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [recording]);
  useEffect(() => {
    if (recording && seconds >= 30) recorder.current?.stop();
  }, [seconds, recording]);

  function close() {
    if (busy) return;
    if (recorder.current?.state === "recording") recorder.current.stop();
    stream.current?.getTracks().forEach(track => track.stop());
    dialog.current?.close();
    setOpenDialog(false);
  }

  function open() {
    audio.current?.pause();
    setPreview("");
    recordingBlob.current = null;
    setError("");
    setSeconds(0);
    setOpenDialog(true);
    dialog.current?.showModal();
  }

  async function record() {
    if (pending.current) return;
    if (recording) { recorder.current?.stop(); return; }
    pending.current = true;
    setError("");
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error("Audio recording is unavailable in this browser.");
      const input = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!dialog.current?.open) { input.getTracks().forEach(track => track.stop()); return; }
      stream.current = input;
      const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/ogg;codecs=opus"].find(type => MediaRecorder.isTypeSupported(type));
      const capture = new MediaRecorder(input, mimeType ? { mimeType, audioBitsPerSecond: 64000 } : undefined);
      recorder.current = capture;
      const chunks: BlobPart[] = [];
      capture.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
      capture.onstop = () => {
        input.getTracks().forEach(track => track.stop());
        setRecording(false);
        const blob = new Blob(chunks, { type: capture.mimeType });
        recordingBlob.current = blob;
        if (dialog.current?.open) setPreview(URL.createObjectURL(blob));
      };
      setPreview("");
      setSeconds(0);
      capture.start();
      setRecording(true);
    } catch (reason) {
      stream.current?.getTracks().forEach(track => track.stop());
      setError(reason instanceof Error ? reason.message : "Microphone access failed.");
    } finally { pending.current = false; }
  }

  async function save(remove = false) {
    if (busy) return;
    setBusy(true);
    setError("");
    audio.current?.pause();
    try {
      const body = new FormData();
      if (!remove && recordingBlob.current) body.append("audio", recordingBlob.current, "voice-sample");
      const response = await fetch("/api/account/voice-profile", { method: remove ? "DELETE" : "PUT", body: remove ? undefined : body });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Voice identity could not be saved.");
      setProfile(current => current && { ...current, enrolled: result.enrolled, playable: result.enrolled });
      setAudioVersion(value => value + 1);
      setOpenDialog(false);
      dialog.current?.close();
      setPreview("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Voice identity could not be saved."); }
    finally { setBusy(false); }
  }

  async function togglePlayback() {
    if (!audio.current) return;
    if (playing) audio.current.pause();
    else {
      try { await audio.current.play(); }
      catch { setError("The voice sample could not be played."); }
    }
  }

  return <div className="mt-6">
    <div className="inline-flex max-w-full items-stretch overflow-hidden rounded-xl border border-stone-300 bg-stone-50 text-stone-800">
      {profile?.enrolled ? <>
        <button type="button" className={`${button} flex items-center gap-2`} disabled={busy || !profile.playable} onClick={() => void togglePlayback()} aria-label={playing ? "Pause voice identity sample" : "Play voice identity sample"}>
          <PlayIcon playing={playing} /><span>Voice identity established</span>
        </button>
        <button type="button" className={`${button} border-l border-stone-300`} disabled={busy || !profile.available} onClick={open}>Re-record</button>
        <button type="button" className={`${button} border-l border-stone-300 hover:bg-red-50 hover:text-red-700`} disabled={busy} onClick={() => void save(true)} aria-label="Delete voice identity" title="Delete voice identity">
          <svg aria-hidden="true" className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7" /></svg>
        </button>
      </> : <button type="button" className={button} onClick={open} disabled={busy || !profile?.available}>{profile ? "Establish voice identity" : "Loading voice identity…"}</button>}
    </div>
    {profile?.enrolled && !profile.playable && <p className="mt-2 text-sm text-stone-600">Re-record to add a playable sample to your existing identity.</p>}
    {profile && !profile.available && <p className="mt-2 text-sm text-stone-600">Voice enrollment is currently unavailable.</p>}
    {busy && <p className="mt-2 text-sm text-stone-600" role="status">Processing voice identity…</p>}
    {error && !openDialog && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
    <audio key={audioVersion} ref={audio} src={profile?.playable ? "/api/account/voice-profile/audio" : undefined} preload="none" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} />
    <dialog ref={dialog} aria-labelledby="voice-title" onCancel={event => { event.preventDefault(); close(); }} onClose={() => { stream.current?.getTracks().forEach(track => track.stop()); }} className="m-auto w-[min(92vw,520px)] rounded-2xl border border-stone-300 bg-stone-50 p-6 text-stone-900 shadow-xl backdrop:bg-black/40">
      <h2 id="voice-title" className="text-lg font-semibold">Establish your voice identity</h2>
      <p className="mt-2 text-sm text-stone-600">Find a quiet place and read aloud in your normal speaking voice. Record about 20–30 seconds with only you speaking.</p>
      <p className="mt-5 text-base leading-7">{prompt}</p>
      <p className="mt-3 text-sm text-stone-600">This sample helps identify you in session transcripts. You can replace or delete it in Account Settings.</p>
      <div className="mt-5 flex min-h-10 items-center justify-center gap-3">
        {recording && <span role="status" className="text-sm text-red-700">Recording · {seconds}s</span>}
        {preview && <audio controls src={preview} className="max-w-full" />}
      </div>
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      <div className="mt-5 flex flex-wrap justify-end gap-2">
        <button type="button" className={`${button} rounded-lg border border-stone-300`} disabled={busy} onClick={close}>Cancel</button>
        <button type="button" className={`${button} rounded-lg border border-stone-300`} disabled={busy} onClick={() => void record()}>{recording ? "Stop recording" : preview ? "Record again" : "Record"}</button>
        {preview && !recording && <button type="button" className={`${button} rounded-lg border border-emerald-700 text-emerald-800`} disabled={busy || seconds < 5} onClick={() => void save()}>Use recording</button>}
      </div>
    </dialog>
  </div>;
}
