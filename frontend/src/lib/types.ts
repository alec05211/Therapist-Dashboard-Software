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
