import { RoleWorkspace } from "@/components/auth/role-workspace";

export default async function ClientPage({ params, searchParams }: {
  params: Promise<{ clientId: string }>;
  searchParams: Promise<{ view?: string | string[] }>;
}) {
  const { clientId } = await params;
  const { view } = await searchParams;
  const initialClientView = view === "chat" ? "chat" : "clinical-workspace";
  return <RoleWorkspace key={`${clientId}:${initialClientView}`} clientId={clientId} initialClientView={initialClientView} />;
}
