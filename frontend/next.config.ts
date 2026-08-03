import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/screenshots/:path*",
        destination: `${apiUrl}/screenshots/:path*`,
      },
    ];
  },
};

export default nextConfig;
