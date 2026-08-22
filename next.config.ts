import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // In local development, proxy /api/* to local FastAPI backend on port 8000.
  // On Vercel production, api/index.py handles /api/* directly as a Serverless Function.
  async rewrites() {
    if (process.env.NODE_ENV === "development" || !process.env.VERCEL) {
      const devBackend = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      if (devBackend.startsWith("http") && !devBackend.includes(":3000")) {
        return [
          {
            source: "/api/:path*",
            destination: `${devBackend}/api/:path*`,
          },
        ];
      }
    }
    return [];
  },
};

export default nextConfig;

