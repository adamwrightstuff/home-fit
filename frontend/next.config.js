/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  eslint: {
    // Don't fail build on ESLint errors during production build
    ignoreDuringBuilds: false,
  },
}

module.exports = nextConfig
