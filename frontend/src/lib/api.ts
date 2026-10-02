import type { ClientJourneyEntry, JobStatus, PersistedInsightSnapshot, PreSessionBrief, ProcessingJob, Transcript, TranscriptListItem } from "@/lib/types";

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
  listProcessingJobs: (clientId: string) => request<ProcessingJob[]>(`/transcription-jobs?${clientQuery(clientId)}`),
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
  uploadRecording: (audio: Blob, clientId: string, appointmentId: string | null, onProgress?: (percent: number) => void) => {
    const form = new FormData();
    form.append("audio", audio, audio instanceof File ? audio.name : "recording.webm");
    return new Promise<{ id: string }>((resolve, reject) => {
      const upload = new XMLHttpRequest();
      const appointmentQuery = appointmentId ? `&appointment_id=${encodeURIComponent(appointmentId)}` : "";
      upload.open("POST", `/api/transcribe?${clientQuery(clientId)}${appointmentQuery}`);
      upload.responseType = "json";
      upload.upload.addEventListener("progress", event => {
        if (event.lengthComputable) onProgress?.(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      });
      upload.addEventListener("load", () => {
        const data = upload.response && typeof upload.response === "object" ? upload.response : {};
        if (upload.status >= 200 && upload.status < 300 && typeof data.id === "string") resolve({ id: data.id });
        else reject(new ApiError(typeof data.detail === "string" ? data.detail : "The recording could not be uploaded.", upload.status));
      });
      upload.addEventListener("error", () => reject(new ApiError("The recording upload was interrupted.", 0)));
      upload.addEventListener("abort", () => reject(new ApiError("The recording upload was cancelled.", 0)));
      upload.send(form);
    });
  },
  saveSpeakerLabels: (id: string, clientId: string, labels: Record<string, string>) =>
    request<{ speakers: Record<string, string> }>(`/transcripts/${encodeURIComponent(id)}/speakers?${clientQuery(clientId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(labels),
    }),
};
