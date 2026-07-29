const path = require('path')

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Include data files from the repo root (outside the frontend/ build root) so
  // Vercel's file tracer bundles them into the catalog-map serverless function.
  outputFileTracingRoot: path.join(__dirname, '../'),
  outputFileTracingIncludes: {
    '/api/catalog-map': [
      '../data/nyc_metro_place_catalog_scores_merged.jsonl',
      '../data/la_metro_place_catalog_scores_merged.jsonl',
      '../data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
    ],
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
