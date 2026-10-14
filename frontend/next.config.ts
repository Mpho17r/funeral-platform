import type { NextConfig } from "next";

// When API_PROXY_TARGET is set (Codespaces), the browser calls
// /backend/* on the app's own port and Next forwards it to the API,
// so no second public port or CORS setup is needed.
const apiProxyTarget = process.env.API_PROXY_TARGET;

const nextConfig: NextConfig = {
  allowedDevOrigins: ["*.app.github.dev"],

  async rewrites() {
    if (!apiProxyTarget) {
      return [];
    }

    return [
      {
        source: "/backend/:path*",
        destination: `${apiProxyTarget}/:path*`,
      },
    ];
  },
};

export default nextConfig;
