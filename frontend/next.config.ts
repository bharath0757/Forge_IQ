import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // If an external backend URL is provided (e.g. Render / Railway), proxy to it.
  // Otherwise, the built-in Next.js App Router API Routes handle all requests natively.
  async rewrites() {
    const externalApi = process.env.NEXT_PUBLIC_API_URL;
    if (externalApi && externalApi.startsWith("http") && !externalApi.includes("localhost:3000")) {
      return [
        {
          source: "/api/:path*",
          destination: `${externalApi}/api/:path*`,
        },
        {
          source: "/health",
          destination: `${externalApi}/health`,
        },
        {
          source: "/health/:path*",
          destination: `${externalApi}/health/:path*`,
        },
      ];
    }
    return [];
  },
};

export default nextConfig;
