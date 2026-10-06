import type { ClientJourneyEntry } from "@/lib/types";

export type JourneyCategory = ClientJourneyEntry["category"];

export const JOURNEY_CATEGORIES: ReadonlyArray<{
  value: JourneyCategory;
  label: string;
}> = [
  { value: "important_quote", label: "Important statement" },
  { value: "resolution", label: "Resolution" },
  { value: "breakthrough", label: "Breakthrough" },
  { value: "context", label: "Relevant context" },
  { value: "theme", label: "Theme to consider" },
  { value: "open_thread", label: "Follow-up for next session" },
];
