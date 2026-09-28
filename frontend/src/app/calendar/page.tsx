import { redirect } from "next/navigation";
import { TherapistCalendar } from "@/components/therapist-calendar";
import { auth0 } from "@/lib/auth0";
import { isAuth0Configured } from "@/lib/auth-config";

export default async function CalendarPage() {
  if (!isAuth0Configured || !(await auth0.getSession())) redirect("/login");
  return <TherapistCalendar />;
}
