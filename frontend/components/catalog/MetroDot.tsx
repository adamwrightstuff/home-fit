'use client'

const METRO_COLOR: Record<'nyc' | 'la' | 'sf' | 'seattle', string> = {
  nyc: '#6B5CE7',
  la: '#E76B5C',
  sf: '#2A9D8F',
  seattle: '#1A8FBF',
}

const METRO_LABEL: Record<'nyc' | 'la' | 'sf' | 'seattle', string> = {
  nyc: 'NYC',
  la: 'LA',
  sf: 'SF',
  seattle: 'SEA',
}

export default function MetroDot({ metro }: { metro: 'nyc' | 'la' | 'sf' | 'seattle' }) {
  return (
    <span
      className="inline-block h-2 w-2 shrink-0 rounded-full"
      style={{ background: METRO_COLOR[metro] }}
      title={METRO_LABEL[metro]}
      aria-hidden
    />
  )
}
