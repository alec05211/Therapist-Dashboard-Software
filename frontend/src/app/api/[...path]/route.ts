import { NextRequest, NextResponse } from "next/server";
import { auth0 } from "@/lib/auth0";

async function forward(request: NextRequest) {
  try {
    if (!await auth0.getSession()) return NextResponse.json({ detail: "Sign in is required." }, { status: 401 });
    const { token } = await auth0.getAccessToken();
    const url = new URL(process.env.API_ORIGIN ?? "http://127.0.0.1:8000");
    url.pathname = request.nextUrl.pathname.slice(4);
    url.search = request.nextUrl.search;
    const headers = new Headers({ Authorization: `Bearer ${token}` });
    for (const key of ["content-type", "range"]) {
      const value = request.headers.get(key);
      if (value) headers.set(key, value);
    }
    const response = await fetch(url, { method: request.method, headers, cache: "no-store", body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer() });
    const outgoing = new Headers({ "Cache-Control": "no-store" });
    for (const key of ["content-type", "content-length", "content-range", "accept-ranges"]) {
      const value = response.headers.get(key);
      if (value) outgoing.set(key, value);
    }
    return new Response(response.body, { status: response.status, headers: outgoing });
  } catch {
    return NextResponse.json({ detail: "The secure service is unavailable." }, { status: 503 });
  }
}
export { forward as GET, forward as POST, forward as PUT, forward as DELETE, forward as HEAD };
