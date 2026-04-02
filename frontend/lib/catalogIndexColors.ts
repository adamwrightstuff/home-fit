/** Catalog map / sheet anchor colors for the four indices (product spec). */
export const CATALOG_INDEX_COLORS = {
  homefit: '#7F77DD',
  longevity: '#1D9E75',
  happiness: '#EF9F27',
  status: '#D85A30',
} as const

export type CatalogIndexColorKey = keyof typeof CATALOG_INDEX_COLORS
