"use client";

import { useRef } from "react";

export function AudioUploadButton({ disabled, onUpload }: { disabled: boolean; onUpload: (file: File) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return <>
    <input ref={input} type="file" accept=".wav,.mp3,.m4a,.mp4,.flac,.ogg,.webm,.amr" className="hidden" aria-label="Choose audio recording" onChange={event => {
      const file = event.target.files?.[0];
      event.target.value = "";
      if (file) onUpload(file);
    }} />
    <button type="button" aria-label="Upload audio recording" title="Upload audio recording" disabled={disabled} onClick={() => input.current?.click()} className="inline-flex size-11 shrink-0 cursor-grab items-center justify-center rounded-xl border border-stone-300 bg-stone-50 text-stone-700 transition-colors duration-200 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing disabled:cursor-not-allowed disabled:opacity-60">
      <svg aria-hidden="true" className="size-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path strokeLinecap="round" strokeLinejoin="round" d="M12 15V3m0 0L7.5 7.5M12 3l4.5 4.5M4.5 15v4.5h15V15" /></svg>
    </button>
  </>;
}
