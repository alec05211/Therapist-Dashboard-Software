import { NextResponse } from "next/server";
import { auth0 } from "@/lib/auth0";

export async function GET() {
  return NextResponse.json({ authenticated: Boolean(await auth0.getSession()) });
}
