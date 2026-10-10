import { NextRequest, NextResponse } from "next/server";

import { auth0 } from "./lib/auth0";

const protectedRoutePrefixes = ["/calendar", "/clients"];

function isProtectedRoute(pathname: string) {
  return protectedRoutePrefixes.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

export async function proxy(request: NextRequest) {
  const authResponse = await auth0.middleware(request);
  const { pathname } = new URL(request.url);

  if (isProtectedRoute(pathname) && !(await auth0.getSession(request))) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return authResponse;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};
