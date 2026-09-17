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
