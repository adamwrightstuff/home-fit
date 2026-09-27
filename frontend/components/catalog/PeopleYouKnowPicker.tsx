'use client'

import { useState } from 'react'
import { Heart, Loader2, Plus, Users, X } from 'lucide-react'
import { type SocialConnectionPerson, geocodePerson } from '@/lib/socialConnections'
import type { SocialConnectionTier } from '@/lib/reweight'

interface PeopleYouKnowPickerProps {
  people: SocialConnectionPerson[]
  onPeopleChange: (people: SocialConnectionPerson[]) => void
}

const TIER_COPY: Record<SocialConnectionTier, { label: string; icon: typeof Heart; sub: string }> = {
  close: { label: 'Close', icon: Heart, sub: 'Family or a close friend' },
  acquaintance: { label: 'Acquaintance', icon: Users, sub: 'Someone you know, casually' },
}

function TierIcon({ tier, size = 14 }: { tier: SocialConnectionTier; size?: number }) {
  const Icon = TIER_COPY[tier].icon
  return <Icon size={size} strokeWidth={2} fill={tier === 'close' ? 'currentColor' : 'none'} />
}

export default function PeopleYouKnowPicker({ people, onPeopleChange }: PeopleYouKnowPickerProps) {
  const [adding, setAdding] = useState(false)
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [tier, setTier] = useState<SocialConnectionTier>('close')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = () => {
    setAdding(false)
    setName('')
    setAddress('')
    setTier('close')
    setError(null)
  }

  const submit = async () => {
    if (!address.trim() || busy) return
    setBusy(true)
    setError(null)
    const res = await geocodePerson(address.trim())
    setBusy(false)
    if ('error' in res) {
      setError(res.error)
      return
    }
    const person: SocialConnectionPerson = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      label: name.trim() || res.address,
      address: res.address,
      lat: res.lat,
      lon: res.lon,
      tier,
    }
    onPeopleChange([...people, person])
    reset()
  }

  const remove = (id: string) => onPeopleChange(people.filter((p) => p.id !== id))

  return (
    <div>
      {people.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
          {people.map((p) => (
            <div
              key={p.id}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '6px 6px 6px 8px', borderRadius: 8,
                border: '1px solid var(--hf-border)', background: 'var(--hf-card-bg)',
                boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
              }}
            >
              <div
                aria-hidden
                style={{
                  width: 28, height: 28, borderRadius: 999, flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: p.tier === 'close' ? 'var(--tr-accent-50)' : 'var(--hf-bg-subtle)',
                  color: p.tier === 'close' ? 'var(--hf-primary-1)' : 'var(--hf-text-secondary)',
                }}
              >
                <TierIcon tier={p.tier} />
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--hf-text-primary)', lineHeight: 1.3 }}>
                  {p.label}
                </div>
                <div style={{ fontSize: 11, color: 'var(--hf-text-secondary)', lineHeight: 1.35, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {TIER_COPY[p.tier].label} · {p.address}
                </div>
              </div>
              <button
                type="button"
                onClick={() => remove(p.id)}
                aria-label={`Remove ${p.label}`}
                style={{
                  width: 24, height: 24, borderRadius: 999, flexShrink: 0, border: 'none', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: 'var(--hf-hover-bg)', color: 'var(--hf-text-secondary)',
                }}
              >
                <X size={13} strokeWidth={2.25} />
              </button>
            </div>
          ))}
        </div>
      )}

      {!adding && (
        <button
          type="button"
          onClick={() => setAdding(true)}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            width: '100%', padding: '10px 12px', borderRadius: 8,
            border: '1px dashed var(--hf-border)', background: 'transparent',
            color: 'var(--hf-text-secondary)', fontSize: 12, fontWeight: 600, cursor: 'pointer',
          }}
        >
          <Plus size={14} strokeWidth={2.25} />
          Add someone
        </button>
      )}

      {adding && (
        <div
          style={{
            display: 'flex', flexDirection: 'column', gap: 8, padding: 10,
            borderRadius: 10, border: '1px solid var(--hf-border)', background: 'var(--hf-card-bg)',
          }}
        >
          <input
            type="text"
            value={name}
            disabled={busy}
            placeholder="Name (optional) — Mom, Sarah…"
            onChange={(e) => setName(e.target.value)}
            className="text-base sm:text-[13px]"
            style={{
              height: 36, padding: '0 10px', borderRadius: 8,
              border: '1px solid var(--hf-border)', background: 'var(--hf-bg-subtle)',
              color: 'var(--hf-text-primary)', outline: 'none',
            }}
          />
          <input
            type="text"
            value={address}
            disabled={busy}
            placeholder="Their address or neighborhood"
            onChange={(e) => { setAddress(e.target.value); setError(null) }}
            onKeyDown={(e) => { if (e.key === 'Enter') submit() }}
            className="text-base sm:text-[13px]"
            style={{
              height: 36, padding: '0 10px', borderRadius: 8,
              border: '1px solid var(--hf-border)', background: 'var(--hf-bg-subtle)',
              color: 'var(--hf-text-primary)', outline: 'none',
            }}
          />
          <div style={{ display: 'flex', gap: 6 }}>
            {(['close', 'acquaintance'] as const).map((t) => {
              const Icon = TIER_COPY[t].icon
              const active = tier === t
              return (
                <button
                  key={t}
                  type="button"
                  disabled={busy}
                  onClick={() => setTier(t)}
                  title={TIER_COPY[t].sub}
                  style={{
                    flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                    padding: '8px 10px', borderRadius: 999, cursor: 'pointer',
                    fontSize: 12, fontWeight: 600,
                    border: `1px solid ${active ? 'var(--hf-primary-1)' : 'var(--hf-border)'}`,
                    background: active ? 'var(--tr-accent-50)' : 'transparent',
                    color: active ? 'var(--hf-primary-1)' : 'var(--hf-text-secondary)',
                  }}
                >
                  <Icon size={13} strokeWidth={2} fill={active && t === 'close' ? 'currentColor' : 'none'} />
                  {TIER_COPY[t].label}
                </button>
              )
            })}
          </div>
          {error && <div role="alert" style={{ fontSize: 11, color: 'var(--hf-danger)' }}>{error}</div>}
          <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
            <button
              type="button"
              onClick={reset}
              disabled={busy}
              style={{
                flex: 1, padding: '8px 10px', borderRadius: 8, cursor: 'pointer',
                fontSize: 12, fontWeight: 600, border: '1px solid var(--hf-border)',
                background: 'transparent', color: 'var(--hf-text-secondary)',
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={submit}
              disabled={busy || !address.trim()}
              style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                padding: '8px 10px', borderRadius: 8, cursor: busy || !address.trim() ? 'default' : 'pointer',
                fontSize: 12, fontWeight: 700, border: 'none',
                background: 'var(--hf-primary-1)', color: 'white',
                opacity: busy || !address.trim() ? 0.5 : 1,
              }}
            >
              {busy ? <Loader2 size={13} className="animate-spin" /> : null}
              {busy ? 'Finding it…' : 'Add'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
