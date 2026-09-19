import { RoleWorkspace } from "@/components/auth/role-workspace";
import { isAuth0Configured } from "@/lib/auth-config";
import { auth0 } from "@/lib/auth0";

export default async function Home() {
  if (!isAuth0Configured || !(await auth0.getSession())) return <main aria-label="Therapist Dashboard" className="min-h-[calc(100vh-4rem)]" />;
  return <RoleWorkspace />;
}
