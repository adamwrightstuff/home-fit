import CatalogMapClient from '../catalog-map-client'

export const metadata = {
  title: 'LA metro catalog map · HomeFit',
  description: 'Explore neighborhood scores across the LA metro catalog.',
}

export default function LaCatalogMapPage() {
  return <CatalogMapClient metro="la" />
}
