import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  async rewrites() {
    const apiOrigin = process.env.BF1_API_ORIGIN?.replace(/\/$/, "");
    return apiOrigin
      ? [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }]
      : [];
  },
};

export default nextConfig;
