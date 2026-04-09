import CatalogMapClient from './catalog-map-client'

export const metadata = {
  title: 'NYC metro catalog map · HomeFit',
  description: 'Explore neighborhood scores across the NYC metro catalog.',
}

export default function CatalogMapPage() {
  return <CatalogMapClient metro="nyc" />
}
