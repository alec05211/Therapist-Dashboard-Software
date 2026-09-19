export type AccountRole = "therapist" | "client";
export type AccountFeature = "profile" | "appearance" | "aboutMe" | "sessionNavigation" | "practiceNavigation";

// One source for which account-setting modules each role can see. The API
// checks permissions independently; hiding a module is never authorization.
export const roleCapabilities: Record<AccountRole, ReadonlySet<AccountFeature>> = {
  therapist: new Set(["profile", "appearance", "aboutMe", "sessionNavigation", "practiceNavigation"]),
  client: new Set(["profile", "appearance"]),
};

export function canUseFeature(role: AccountRole, feature: AccountFeature): boolean {
  return roleCapabilities[role].has(feature);
}
