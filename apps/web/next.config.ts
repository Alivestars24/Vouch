import type { NextConfig } from "next";
import path from "node:path";

const internalApiOrigin = process.env.VOUCH_INTERNAL_API_ORIGIN?.replace(/\/$/, "");

if (internalApiOrigin) {
  const parsed = new URL(internalApiOrigin);
  const loopback = ["127.0.0.1", "localhost", "::1"].includes(parsed.hostname);
  if (
    parsed.username
    || parsed.password
    || !parsed.hostname
    || !["", "/"].includes(parsed.pathname)
    || parsed.search
    || parsed.hash
    || (parsed.protocol !== "https:" && !(parsed.protocol === "http:" && loopback))
  ) {
    throw new Error(
      "VOUCH_INTERNAL_API_ORIGIN must be a credential-free HTTPS origin (HTTP only for loopback).",
    );
  }
}

const browserSecurityHeaders = [
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "Permissions-Policy", value: "camera=(), geolocation=(), microphone=()" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    return internalApiOrigin
      ? [{ source: "/api/:path*", destination: `${internalApiOrigin}/api/:path*` }]
      : [];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: browserSecurityHeaders,
      },
      {
        source: "/creator/:path*",
        headers: [
          { key: "Cache-Control", value: "private, no-store, max-age=0" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" },
        ],
      },
    ];
  },
  turbopack: {
    root: path.resolve(import.meta.dirname, "../.."),
  },
};

export default nextConfig;
