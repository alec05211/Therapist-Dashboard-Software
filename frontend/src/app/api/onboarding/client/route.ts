import { NextResponse } from "next/server";
import { auth0 } from "@/lib/auth0";

export async function POST(request: Request) {
  const session = await auth0.getSession();
  if (!session) return NextResponse.json({ detail: "Sign in is required." }, { status: 401 });
  try {
    const { token } = await auth0.getAccessToken();
    const input = await request.json();
    const response = await fetch(`${process.env.API_ORIGIN ?? "http://127.0.0.1:8000"}/onboarding/client`, {
      method: "POST", cache: "no-store", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ first_name: input.first_name, last_name: input.last_name, discoverable: input.discoverable, email: typeof session.user.email === "string" ? session.user.email : null }),
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch { return NextResponse.json({ detail: "The secure client onboarding service is unavailable." }, { status: 503 }); }
}
