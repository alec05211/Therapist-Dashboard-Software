import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { isAuth0Configured } from "@/lib/auth-config";
import { RoleWorkspace } from "@/components/auth/role-workspace";

export default async function ClientPage({ params }: { params: Promise<{ clientId: string }> }) {
  if (!isAuth0Configured || !(await auth0.getSession())) redirect("/login");
  const { clientId } = await params;
  return <RoleWorkspace key={clientId} clientId={clientId} />;
}
