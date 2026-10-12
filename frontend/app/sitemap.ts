import type { MetadataRoute } from 'next'
import { loadAllNeighborhoods } from '@/lib/catalogServer'

const SITE_URL = 'https://www.trovamo.co'

export default function sitemap(): MetadataRoute.Sitemap {
  const neighborhoods = loadAllNeighborhoods()
  return neighborhoods.map((entry) => ({
    url: `${SITE_URL}/neighborhoods/${entry.slug}`,
    lastModified: new Date(),
    changeFrequency: 'monthly',
    priority: 0.7,
  }))
}
