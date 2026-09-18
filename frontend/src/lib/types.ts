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

export type JobStatus = {
  id: string;
  status: string;
  detail?: string;
};

export type BriefEvidence = {
  evidence_id: string;
  session_id: string;
  session_label: string;
  segment_index: number;
  start: number;
  end: number;
  quote: string;
};

export type PreSessionBrief = {
  status: string;
  review_note: string;
  sections: Array<{
    title: string;
    items: Array<{
      text: string;
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

export type PersistedInsightEvidence = {
  evidence_role: "supporting" | "contrasting" | "context";
  transcript_segment_id?: string;
  clinical_note_version_id?: string;
  session_id?: string;
  segment_index?: number;
  start?: number;
  end?: number;
  quote?: string;
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
