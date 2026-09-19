import { NextResponse } from "next/server";
import { auth0 } from "@/lib/auth0";

export async function GET() {
  const session = await auth0.getSession();
  if (!session) return NextResponse.json({ detail: "Sign in is required." }, { status: 401 });
  try {
    const { token } = await auth0.getAccessToken();
    const response = await fetch(`${process.env.API_ORIGIN}/identity/me`, { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch {
    return NextResponse.json({ detail: "The secure identity service is not configured." }, { status: 503 });
  }
}
