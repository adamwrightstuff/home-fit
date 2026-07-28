'use client'

const METRO_COLOR: Record<'nyc' | 'la' | 'sf', string> = {
  nyc: '#6B5CE7',
  la: '#E76B5C',
  sf: '#2A9D8F',
}

const METRO_LABEL: Record<'nyc' | 'la' | 'sf', string> = {
  nyc: 'NYC',
  la: 'LA',
  sf: 'SF',
}

export default function MetroDot({ metro }: { metro: 'nyc' | 'la' | 'sf' }) {
  return (
    <span
      className="inline-block h-2 w-2 shrink-0 rounded-full"
      style={{ background: METRO_COLOR[metro] }}
      title={METRO_LABEL[metro]}
      aria-hidden
    />
  )
}
