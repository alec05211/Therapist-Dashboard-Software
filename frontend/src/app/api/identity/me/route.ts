import { NextResponse } from "next/server";
import { auth0 } from "@/lib/auth0";

export async function GET() {
  const session = await auth0.getSession();
  if (!session) return NextResponse.json({ detail: "Sign in is required." }, { status: 401 });
  try {
    const { token } = await auth0.getAccessToken();
    const apiOrigin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";
    const response = await fetch(`${apiOrigin}/identity/me`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" });
    const body = await response.json().catch(() => null);
    if (!body || response.status >= 500) {
      return NextResponse.json({ detail: "The workspace service is temporarily unavailable. Please try again shortly." }, { status: 503 });
    }
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json({ detail: "Your workspace could not be loaded. Try again, or sign out and sign in again if the problem continues." }, { status: 503 });
  }
}
