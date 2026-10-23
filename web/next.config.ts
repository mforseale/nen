import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  agentRules: false,
  output: "standalone",
  outputFileTracingRoot: path.resolve(__dirname),
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${process.env.NEN_API_ORIGIN ?? "http://127.0.0.1:8000"}/api/v1/:path*` }];
  },
  experimental: {
    proxyClientMaxBodySize: 60 * 1024 * 1024,
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
