import { RoleWorkspace } from "@/components/auth/role-workspace";
import { PublicLanding } from "@/components/public-landing";
import { isAuth0Configured } from "@/lib/auth-config";
import { auth0 } from "@/lib/auth0";

export default async function Home() {
  if (!isAuth0Configured || !(await auth0.getSession())) return <PublicLanding />;
  return <RoleWorkspace />;
}
