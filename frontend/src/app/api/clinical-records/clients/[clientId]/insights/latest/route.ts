import { NextResponse } from "next/server";

import { auth0 } from "@/lib/auth0";

type Context = { params: Promise<{ clientId: string }> };

export async function GET(request: Request, { params }: Context) {
  const session = await auth0.getSession();
  if (!session) {
    return NextResponse.json({ detail: "Sign in is required." }, { status: 401 });
  }

  const organizationId = new URL(request.url).searchParams.get("organization_id");
  if (!organizationId) {
    return NextResponse.json({ detail: "organization_id is required." }, { status: 400 });
  }

  try {
    const { clientId } = await params;
    const { token } = await auth0.getAccessToken();
    const apiOrigin = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";
    const response = await fetch(
      `${apiOrigin}/clinical-records/clients/${encodeURIComponent(clientId)}/insight-snapshots/latest?organization_id=${encodeURIComponent(organizationId)}`,
      {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      },
    );
    const body = await response.json().catch(() => ({ detail: "The API returned an invalid response." }));
    return NextResponse.json(body, { status: response.status });
  } catch {
    return NextResponse.json(
      { detail: "The secure longitudinal-record service is not configured yet." },
      { status: 503 },
    );
  }
}
