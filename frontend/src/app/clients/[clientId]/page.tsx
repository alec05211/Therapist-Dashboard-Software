import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { isAuth0Configured } from "@/lib/auth-config";
import { RoleWorkspace } from "@/components/auth/role-workspace";

export default async function ClientPage({ params, searchParams }: {
  params: Promise<{ clientId: string }>;
  searchParams: Promise<{ view?: string | string[] }>;
}) {
  if (!isAuth0Configured || !(await auth0.getSession())) redirect("/login");
  const { clientId } = await params;
  const { view } = await searchParams;
  const initialClientView = view === "chat" ? "chat" : "clinical-workspace";
  return <RoleWorkspace key={`${clientId}:${initialClientView}`} clientId={clientId} initialClientView={initialClientView} />;
}
