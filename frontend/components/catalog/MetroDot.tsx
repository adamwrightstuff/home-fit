'use client'

export default function MetroDot({ metro }: { metro: 'nyc' | 'la' }) {
  const c = metro === 'nyc' ? '#6B5CE7' : '#E76B5C'
  return (
    <span
      className="inline-block h-2 w-2 shrink-0 rounded-full"
      style={{ background: c }}
      title={metro === 'nyc' ? 'NYC' : 'LA'}
      aria-hidden
    />
  )
}
