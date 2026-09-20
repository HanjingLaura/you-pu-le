import path from "path";
import type { NextConfig } from "next";

const backend =
  process.env.KEYPRINT_BACKEND_URL ?? "http://127.0.0.1:8000";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  skipTrailingSlashRedirect: Boolean(basePath),
  ...(basePath ? { basePath } : {}),
  allowedDevOrigins: [
    "civilian-fiscal-appliance-nickel.trycloudflare.com",
    "opening-wars-cardiff-facts.trycloudflare.com",
    "*.trycloudflare.com",
    "curvy-breads-do.loca.lt",
    "eager-suits-heal.loca.lt",
    "*.loca.lt",
    "loca.lt",
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
      { source: "/key-transpose", destination: `${backend}/key-transpose` },
      { source: "/key-transpose/:path*", destination: `${backend}/key-transpose/:path*` },
    ];
  },
};

export default nextConfig;
