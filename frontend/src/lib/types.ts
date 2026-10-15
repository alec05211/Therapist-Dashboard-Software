export type TranscriptSegment = {
  start: number;
  end: number;
  text: string;
  speaker?: string;
};

export type ClinicalNoteSection = {
  name: string;
  items: string[];
};

export type ClinicalNoteVersion = {
  id: string;
  parent_version_id?: string | null;
  version_number: number;
  status: "draft" | "reviewed" | "finalized";
  content: {
    schema_version: number;
    editor: "tiptap";
    document: Record<string, unknown>;
    plain_text: string;
  };
  finalized_at?: string | null;
  created_at?: string;
};

export type Transcript = {
  id?: string;
  segments: TranscriptSegment[];
  speakers: Record<string, string>;
  clinical_note: ClinicalNoteSection[];
  recording_url?: string;
};

export type TranscriptListItem = {
  id: string;
  label: string;
  text: string;
  created_at: string;
};

export type Appointment = {
  id: string;
  organization_id: string;
  client_id: string;
  client_name?: string | null;
  starts_at: string;
  ends_at: string;
  status: "scheduled" | "confirmed" | "cancelled" | "completed" | "no_show";
  appointment_type: "recurring" | "make_up" | "one_time";
  meeting_mode: "in_person" | "video" | "phone";
  series_id?: string | null;
};

export type JobStatus = {
  id: string;
  status: string;
  detail?: string;
};

export type ProcessingJob = JobStatus & {
  appointment_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type SessionProcessingState = {
  phase: "uploading" | "processing";
  message: string;
  progress: number | null;
};

export type BriefEvidence = {
  evidence_id: string;
  session_id: string;
  session_label: string;
  segment_index?: number;
  start?: number;
  end?: number;
  quote?: string;
};

export type PreSessionBrief = {
  status: string;
  review_note: string;
  sections: Array<{
    title: string;
    items: Array<{
      text: string;
      claims?: Array<{ phrase: string; occurrence: number; scope: "single_exchange" | "cross_session"; evidence_ids: string[]; sources: BriefEvidence[] }>;
      sources: BriefEvidence[];
    }>;
  }>;
};

export type ClientInsights = {
  status: string;
  review_note: string;
  narrative: string;
  records: Array<{
    session_id: string;
    session_label: string;
    note_status: string;
    included: boolean;
  }>;
  patterns: Array<{
    id: string;
    title: string;
    summary: string;
    evidence: BriefEvidence[];
    status: string;
  }>;
  open_threads: Array<{
    text: string;
    evidence: BriefEvidence[];
  }>;
  context_packet: {
    purpose: string;
    selection_policy: string;
    items: Array<{
      kind: string;
      text: string;
      evidence: BriefEvidence[];
    }>;
    records: ClientInsights["records"];
  };
};

export type LongitudinalRecordContext = {
  organizationId: string;
  clientId: string;
};

export type ClientJourneyEntry = {
  id: string;
  session_id: string;
  source_provider: string;
  category: "context" | "theme" | "important_quote" | "resolution" | "breakthrough" | "open_thread";
  categories: Array<ClientJourneyEntry["category"]>;
  text: string;
  status: "proposed" | "accepted" | "rejected" | "hidden" | "stale" | "disputed";
  created_at: string;
  evidence: BriefEvidence[];
};

export type PersistedInsightEvidence = {
  evidence_role: "supporting" | "contrasting" | "context";
  transcript_segment_id?: string;
  clinical_note_version_id?: string;
  session_id?: string;
  session_label?: string;
  segment_index?: number;
  start?: number;
  end?: number;
  quote?: string;
};

export type PersistedInsightClaim = {
  phrase: string;
  occurrence: number;
  evidence_ids: string[];
};

export type PersistedInsightContext = {
  text: string;
  claims: PersistedInsightClaim[];
};

export type PersistedInsightSnapshot = {
  id: string;
  version: number;
  status: "draft" | "reviewed" | "accepted" | "rejected" | "superseded";
  generator_name: string;
  generator_version?: string | null;
  selection_policy_version: string;
  content: Record<string, unknown>;
  created_at: string;
  reviewed_at?: string | null;
  items: Array<{
    id: string;
    kind: "trajectory" | "theme" | "open_thread" | "relevant_history" | "client_context" | "therapist_curated";
    review_state: "draft" | "accepted" | "hidden" | "stale" | "disputed";
    display_order: number;
    content: Record<string, unknown>;
    evidence: PersistedInsightEvidence[];
  }>;
};

export type InsightsRefreshStatus = {
  status: "idle" | "pending" | "running" | "failed";
  desired_insights_revision: number;
  published_insights_revision: number;
  published_insight_snapshot_id?: string | null;
  pending_event_count: number;
  pending_since?: string | null;
  last_event_at?: string | null;
  last_published_at?: string | null;
  last_error_code?: string | null;
};
