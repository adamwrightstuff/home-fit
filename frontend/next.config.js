const path = require('path')

// Pre-scored catalog JSONL files (copied into frontend/data/ by the Vercel
// buildCommand before next build runs). Needed by any route that reads the
// catalog at build/request time.
const CATALOG_DATA_FILES = [
  // BEGIN GENERATED files (scripts/metro_agent/registry.py; do not edit by hand)
  'data/nyc_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  'data/la_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  'data/sf_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  'data/seattle_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  'data/austin_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  'data/chicago_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  'data/philadelphia_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  'data/dallas_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  'data/houston_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  'data/phoenix_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  'data/san_antonio_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  'data/sacramento_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  'data/las_vegas_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  'data/orlando_metro_place_catalog_scores_merged.composites_recomputed.jsonl',
  // END GENERATED files
  'data/catalog_climate_profiles.jsonl',
]

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // Tell the file tracer to bundle the catalog JSONL files (copied into
    // frontend/data/ by the Vercel buildCommand before next build runs).
    outputFileTracingIncludes: {
      '/api/catalog-map': CATALOG_DATA_FILES,
      '/neighborhoods/[slug]': CATALOG_DATA_FILES,
      '/sitemap.xml': CATALOG_DATA_FILES,
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
