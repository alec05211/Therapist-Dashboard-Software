import type { NextConfig } from "next";

// API requests must pass through the authenticated route handlers. A rewrite
// runs before dynamic routes and would bypass the catch-all's bearer token.
const nextConfig: NextConfig = {};

export default nextConfig;
