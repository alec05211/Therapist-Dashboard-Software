import { NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";

export async function POST(request: Request) {
  const session = await auth0.getSession();
  if (!session) {
    return NextResponse.json({ detail: "Sign in is required." }, { status: 401 });
  }

  try {
    const { token } = await auth0.getAccessToken();
    const apiOrigin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";
    const response = await fetch(`${apiOrigin}/onboarding/therapist`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(await request.json()),
      cache: "no-store",
    });

    const body = await response.json().catch(() => ({ detail: "The API returned an invalid response." }));
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "The secure onboarding service is not configured yet." },
      { status: 503 },
    );
  }
}
