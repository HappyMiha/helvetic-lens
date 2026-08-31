import type { NextConfig } from "next";
import path from "node:path";

const config: NextConfig = {
  output: "standalone",
  // Model requests can take longer than Next's default 30-second proxy timeout.
  experimental: { proxyTimeout: 330000 },
  outputFileTracingRoot: path.join(process.cwd(), "../.."),
  async rewrites() {
    const api = (
      process.env.REGWATCH_API_URL || "http://127.0.0.1:8000"
    ).replace(/\/$/, "");
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};
export default config;
