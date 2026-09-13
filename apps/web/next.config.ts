import type { NextConfig } from "next";
import path from "node:path";
import assert from "node:assert/strict";

// A separate local check build leaves an already-running browser check intact.
const checkBuild = process.env.HELVETIC_LENS_CHECK_BUILD;
if (checkBuild) assert.match(checkBuild, /^[a-z0-9-]{1,64}$/);
const config: NextConfig = {
  distDir: checkBuild ? `.next-check-${checkBuild}` : ".next",
  output: "standalone",
  // Model requests can take longer than Next's default 30-second proxy timeout.
  experimental: { proxyTimeout: 330000 },
  outputFileTracingRoot: path.join(process.cwd(), "../.."),
  async rewrites() {
    const api = (
      process.env.HELVETIC_LENS_API_URL ||
      process.env.REGWATCH_API_URL ||
      "http://127.0.0.1:8000"
    ).replace(/\/$/, "");
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};
export default config;
