const path = require('path')

// The catalog list and per-place detail are served by the API (catalog_api.py on Railway), not bundled here: every
// deployment used to carry ~111 MB of catalog JSONL, which pushed the Vercel Hobby team over its storage limits.
// The browser still calls /api/catalog-map/all and /api/catalog-map?metro=X&key=Y; these rewrites forward them.
const API_BASE = (process.env.RAILWAY_API_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: '/api/catalog-map/all', destination: `${API_BASE}/catalog/list` },
      { source: '/api/catalog-map', destination: `${API_BASE}/catalog/place` },
    ]
  },
  experimental: {
    // Keep the repo-level data/ folder (backups, working files) out of the function bundles.
    outputFileTracingExcludes: {
      '*': ['../data/**/*'],
    },
  },
  eslint: {
    // Don't fail build on ESLint errors during production build
    ignoreDuringBuilds: false,
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'images.unsplash.com',
        pathname: '/**',
      },
    ],
  },
}

module.exports = nextConfig
