'use client';

export type TravelerProfile = 'adventurer' | 'relaxer' | 'culture' | 'family' | 'remote_worker';

const PROFILES = [
  { value: 'adventurer'    as TravelerProfile, emoji: '🧗', label: 'Adventurer',  tagline: 'Trails & peaks' },
  { value: 'relaxer'       as TravelerProfile, emoji: '🌿', label: 'Relaxer',     tagline: 'Scenery & calm' },
  { value: 'culture'       as TravelerProfile, emoji: '🎭', label: 'Culture',     tagline: 'Food & art' },
  { value: 'family'        as TravelerProfile, emoji: '👨‍👩‍👧', label: 'Family',     tagline: 'Safe & fun' },
  { value: 'remote_worker' as TravelerProfile, emoji: '💻', label: 'Remote Work', tagline: 'Extended stay' },
];

interface Props {
  value: TravelerProfile | null;
  onChange: (v: TravelerProfile | null) => void;
}

export default function TravelerProfileSelector({ value, onChange }: Props) {
  return (
    <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 2 }}>
      {PROFILES.map((p) => {
        const active = value === p.value;
        return (
          <button
            key={p.value}
            type="button"
            onClick={() => onChange(active ? null : p.value)}
            aria-pressed={active}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 4,
              flexShrink: 0,
              width: 80,
              padding: '10px 6px 9px',
              borderRadius: 14,
              border: active ? '2px solid var(--hf-primary-1)' : '2px solid var(--hf-border)',
              background: active ? 'var(--hf-hover-bg)' : 'var(--hf-surface, #fff)',
              cursor: 'pointer',
              transition: 'border-color 0.15s, background 0.15s',
              WebkitTapHighlightColor: 'transparent',
            }}
          >
            <span style={{ fontSize: 22, lineHeight: 1 }}>{p.emoji}</span>
            <span style={{
              fontSize: 11,
              fontWeight: 600,
              color: active ? 'var(--hf-primary-1)' : 'var(--hf-text-primary)',
              letterSpacing: '-0.01em',
            }}>
              {p.label}
            </span>
            <span style={{
              fontSize: 10,
              color: 'var(--hf-text-tertiary)',
              lineHeight: 1.2,
              textAlign: 'center',
            }}>
              {p.tagline}
            </span>
          </button>
        );
      })}
    </div>
  );
}
