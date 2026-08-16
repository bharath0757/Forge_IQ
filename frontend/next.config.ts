import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // In production (Vercel), NEXT_PUBLIC_API_URL must be set to the deployed backend URL.
    // Locally, it defaults to http://localhost:8000.
    const backendUrl =
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
      {
        source: "/health/:path*",
        destination: `${backendUrl}/health/:path*`,
      },
    ];
  },
};

export default nextConfig;
