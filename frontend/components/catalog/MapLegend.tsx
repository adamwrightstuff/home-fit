'use client'

import { catalogModeToRamp, RAMP_HEX } from '@/lib/indexColorSystem'
import type { CatalogMapIndexMode } from '@/lib/catalogMapTypes'

interface MapLegendProps {
  show: boolean
  indexMode?: CatalogMapIndexMode
}

export default function MapLegend({ show, indexMode = 'homefit' }: MapLegendProps) {
  if (!show) return null

  const ramp = RAMP_HEX[catalogModeToRamp(indexMode)]

  return (
    <div
      aria-label="Map score legend"
      style={{
        position: 'absolute',
        top: 60,
        left: 16,
        zIndex: 10,
        background: '#fff',
        border: '1px solid #f3f4f6',
        borderRadius: 12,
        padding: '6px 12px',
        fontSize: 11,
        boxShadow: '0 1px 4px rgba(0,0,0,0.10)',
        pointerEvents: 'none',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
        <span style={{ color: ramp[400], fontSize: 14, lineHeight: 1 }}>●</span>
        <span style={{ color: '#374151' }}>Score 75+</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
        <span style={{ color: ramp[200], fontSize: 14, lineHeight: 1 }}>●</span>
        <span style={{ color: '#374151' }}>Score 50–74</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
        <span style={{ color: ramp[50], fontSize: 14, lineHeight: 1 }}>●</span>
        <span style={{ color: '#374151' }}>Score &lt;50</span>
      </div>
      <div style={{ color: '#9ca3af', fontSize: 10, marginTop: 2 }}>Bubble size = score</div>
    </div>
  )
}
