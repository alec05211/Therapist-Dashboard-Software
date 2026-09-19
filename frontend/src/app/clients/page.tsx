import { redirect } from "next/navigation";
import { auth0 } from "@/lib/auth0";
import { isAuth0Configured } from "@/lib/auth-config";
import { ClientList } from "@/components/client-list";

export default async function ClientsPage() {
  if (!isAuth0Configured || !(await auth0.getSession())) redirect("/login");
  return <ClientList />;
}
