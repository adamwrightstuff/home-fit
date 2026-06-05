'use client'

interface MapLegendProps {
  show: boolean
}

export default function MapLegend({ show }: MapLegendProps) {
  if (!show) return null

  return (
    <div
      aria-label="Map score legend"
      style={{
        position: 'absolute',
        top: 16,
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
        <span style={{ color: '#5B21B6', fontSize: 14, lineHeight: 1 }}>●</span>
        <span style={{ color: '#374151' }}>Score 80+</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
        <span style={{ color: '#8B5CF6', fontSize: 14, lineHeight: 1 }}>●</span>
        <span style={{ color: '#374151' }}>Score 65–79</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
        <span style={{ color: '#C4B5FD', fontSize: 14, lineHeight: 1 }}>●</span>
        <span style={{ color: '#374151' }}>Score &lt;65</span>
      </div>
      <div style={{ color: '#9ca3af', fontSize: 10, marginTop: 2 }}>Bubble size = score</div>
    </div>
  )
}
