import path from "path";
import type { NextConfig } from "next";

const backend =
  process.env.KEYPRINT_BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: [
    "*.trycloudflare.com",
    "*.loca.lt",
    "*.ngrok-free.app",
    "*.ngrok.io",
  ],
  turbopack: {
    root: path.join(__dirname),
  },
  async rewrites() {
    return [
      { source: "/health", destination: `${backend}/health` },
      { source: "/instruments", destination: `${backend}/instruments` },
      { source: "/demo/:path*", destination: `${backend}/demo/:path*` },
      { source: "/jobs", destination: `${backend}/jobs` },
      { source: "/jobs/:path*", destination: `${backend}/jobs/:path*` },
    ];
  },
};

export default nextConfig;
