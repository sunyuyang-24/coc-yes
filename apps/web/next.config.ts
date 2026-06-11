import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@coc-yes/shared"],
  devIndicators: false,
};

export default nextConfig;
