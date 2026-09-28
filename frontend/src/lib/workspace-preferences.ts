export type SessionView = "cards" | "legacy";

const sessionViewKey = "therapist-dashboard-session-view";
export const sessionViewChanged = "therapist-dashboard-session-view-changed";
const sessionCadenceKey = "therapist-dashboard-session-cadence";
export const sessionCadenceChanged = "therapist-dashboard-session-cadence-changed";

export type ClinicalSessionSelection = { id: string; type: "completed" | "scheduled" };

function clinicalSessionKey(clientId: string) {
  return `therapist-dashboard-clinical-session:${clientId}`;
}

export function readClinicalSession(clientId: string): ClinicalSessionSelection | null {
  try {
    const value = JSON.parse(window.localStorage.getItem(clinicalSessionKey(clientId)) ?? "null") as Partial<ClinicalSessionSelection> | null;
    return value && typeof value.id === "string" && (value.type === "completed" || value.type === "scheduled") ? value as ClinicalSessionSelection : null;
  } catch { return null; }
}

export function rememberClinicalSession(clientId: string, selection: ClinicalSessionSelection) {
  window.localStorage.setItem(clinicalSessionKey(clientId), JSON.stringify(selection));
}

export function readSessionView(): SessionView {
  return window.localStorage.getItem(sessionViewKey) === "legacy" ? "legacy" : "cards";
}

export function subscribeToSessionView(onStoreChange: () => void) {
  window.addEventListener(sessionViewChanged, onStoreChange);
  return () => window.removeEventListener(sessionViewChanged, onStoreChange);
}

export function chooseSessionView(view: SessionView) {
  window.localStorage.setItem(sessionViewKey, view);
  window.dispatchEvent(new Event(sessionViewChanged));
}

export function readSessionCadence() {
  return window.localStorage.getItem(sessionCadenceKey) || "Thursdays · 3:00 PM · 50 minutes";
}

export function subscribeToSessionCadence(onStoreChange: () => void) {
  window.addEventListener(sessionCadenceChanged, onStoreChange);
  return () => window.removeEventListener(sessionCadenceChanged, onStoreChange);
}

export function chooseSessionCadence(cadence: string) {
  window.localStorage.setItem(sessionCadenceKey, cadence);
  window.dispatchEvent(new Event(sessionCadenceChanged));
}
