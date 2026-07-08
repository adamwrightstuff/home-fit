'use client';

interface MapEmbedProps {
  lat: number;
  lon: number;
  label?: string;
  zoom?: number;
}

export default function MapEmbed({ lat, lon, label, zoom = 11 }: MapEmbedProps) {
  const marker = `${lat},${lon}`;
  const src = `https://www.openstreetmap.org/export/embed.html?bbox=${lon - 0.15},${lat - 0.1},${lon + 0.15},${lat + 0.1}&layer=mapnik&marker=${marker}`;

  return (
    <div className="hf-card" style={{ padding: 0, overflow: 'hidden', borderRadius: 20 }}>
      {label && (
        <div style={{ padding: '0.75rem 1.25rem', fontSize: '0.875rem', fontWeight: 600, color: 'var(--hf-text-primary)', borderBottom: '1px solid var(--hf-border)' }}>
          📍 {label}
        </div>
      )}
      <iframe
        src={src}
        title="Destination map"
        width="100%"
        height="260"
        style={{ display: 'block', border: 'none' }}
        loading="lazy"
        referrerPolicy="no-referrer"
      />
    </div>
  );
}
