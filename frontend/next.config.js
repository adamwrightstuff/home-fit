const path = require('path')

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // Tell the file tracer to bundle the catalog JSONL files (copied into
    // frontend/data/ by the Vercel buildCommand before next build runs).
    outputFileTracingIncludes: {
      '/api/catalog-map': [
        'data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
        'data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
        'data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
        'data/catalog_climate_profiles.jsonl',
      ],
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
