import type { ClientJourneyEntry, JobStatus, PersistedInsightSnapshot, PreSessionBrief, Transcript, TranscriptListItem } from "@/lib/types";

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new ApiError(data.detail || "The request could not be completed.", response.status);
  }

  return data as T;
}

function clientQuery(clientId: string) {
  return `client_id=${encodeURIComponent(clientId)}`;
}

function normalizeTranscript(transcript: Transcript, clientId: string): Transcript {
  return {
    ...transcript,
    segments: transcript.segments ?? [],
    speakers: transcript.speakers ?? {},
    clinical_note: transcript.clinical_note ?? [],
    recording_url: transcript.recording_url
      ? `/api${transcript.recording_url}${transcript.recording_url.includes("?") ? "&" : "?"}${clientQuery(clientId)}`
      : undefined,
  };
}

export const api = {
  listTranscripts: (clientId: string) => request<TranscriptListItem[]>(`/transcripts?${clientQuery(clientId)}`),
  getTranscript: async (id: string, clientId: string) => normalizeTranscript(
    await request<Transcript>(`/transcripts/${encodeURIComponent(id)}?${clientQuery(clientId)}`), clientId,
  ),
  getJobStatus: (id: string, clientId: string) => request<JobStatus>(`/transcripts/${encodeURIComponent(id)}/status?${clientQuery(clientId)}`),
  getCurrentPreSessionBrief: (organizationId: string, clientId: string) =>
    request<PreSessionBrief>(`/clinical-records/clients/${encodeURIComponent(clientId)}/pre-session-brief?organization_id=${encodeURIComponent(organizationId)}`, { cache: "no-store" }),
  getLatestInsightSnapshot: (organizationId: string, clientId: string) =>
    request<PersistedInsightSnapshot>(
      `/clinical-records/clients/${encodeURIComponent(clientId)}/insight-snapshots/latest?organization_id=${encodeURIComponent(organizationId)}`,
    ),
  getClientJourney: (organizationId: string, clientId: string) =>
    request<{ entries: ClientJourneyEntry[] }>(`/clinical-records/clients/${encodeURIComponent(clientId)}/journey-entries?organization_id=${encodeURIComponent(organizationId)}`),
  reviewClientJourneyEntry: (organizationId: string, clientId: string, entryId: string, update: Pick<ClientJourneyEntry, "category" | "text"> & { status: "accepted" | "rejected" | "hidden" | "stale" | "disputed" }) =>
    request<{ id: string; status: string }>(`/clinical-records/clients/${encodeURIComponent(clientId)}/journey-entries/${encodeURIComponent(entryId)}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ organization_id: organizationId, ...update }),
    }),
  uploadRecording: (audio: Blob, clientId: string) => {
    const form = new FormData();
    form.append("audio", audio, audio instanceof File ? audio.name : "recording.webm");
    return request<{ id: string }>(`/transcribe?${clientQuery(clientId)}`, { method: "POST", body: form });
  },
  saveSpeakerLabels: (id: string, clientId: string, labels: Record<string, string>) =>
    request<{ speakers: Record<string, string> }>(`/transcripts/${encodeURIComponent(id)}/speakers?${clientQuery(clientId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(labels),
    }),
};
