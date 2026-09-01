import type { JobStatus, Transcript, TranscriptListItem } from "@/lib/types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || "The request could not be completed.");
  }

  return data as T;
}

function normalizeTranscript(transcript: Transcript): Transcript {
  return {
    ...transcript,
    segments: transcript.segments ?? [],
    speakers: transcript.speakers ?? {},
    clinical_note: transcript.clinical_note ?? [],
    recording_url: transcript.recording_url ? `/api${transcript.recording_url}` : undefined,
  };
}

export const api = {
  listTranscripts: () => request<TranscriptListItem[]>("/transcripts"),
  getTranscript: async (id: string) => normalizeTranscript(await request<Transcript>(`/transcripts/${encodeURIComponent(id)}`)),
  getJobStatus: (id: string) => request<JobStatus>(`/transcripts/${encodeURIComponent(id)}/status`),
  uploadRecording: (audio: Blob) => {
    const form = new FormData();
    form.append("audio", audio, "recording.webm");
    return request<{ id: string }>("/transcribe", { method: "POST", body: form });
  },
  saveSpeakerLabels: (id: string, labels: Record<string, string>) =>
    request<{ speakers: Record<string, string> }>(`/transcripts/${encodeURIComponent(id)}/speakers`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(labels),
    }),
};
