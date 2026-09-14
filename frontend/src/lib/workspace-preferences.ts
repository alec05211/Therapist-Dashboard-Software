export type SessionView = "cards" | "legacy";

const sessionViewKey = "therapist-dashboard-session-view";
export const sessionViewChanged = "therapist-dashboard-session-view-changed";
const sessionCadenceKey = "therapist-dashboard-session-cadence";
export const sessionCadenceChanged = "therapist-dashboard-session-cadence-changed";

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
