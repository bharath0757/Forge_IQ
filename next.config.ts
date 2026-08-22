import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // If an external backend URL is provided (e.g. Render / local FastAPI on 8000), proxy to it in dev.
  // On Vercel, native Serverless Functions in api/ handle /api/* requests directly.
  async rewrites() {
    const externalApi = process.env.NEXT_PUBLIC_API_URL;
    if (externalApi && externalApi.startsWith("http") && !externalApi.includes("localhost:3000")) {
      return [
        {
          source: "/api/:path*",
          destination: `${externalApi}/api/:path*`,
        },
      ];
    }
    return [];
  },
};

export default nextConfig;
