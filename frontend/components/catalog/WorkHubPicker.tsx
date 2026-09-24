'use client'

import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Briefcase, Building2, Loader2, MapPin, Search, X } from 'lucide-react'
import { type WorkZone, type WorkZoneMetro } from '@/lib/workZones'

export type WorkAddressResult = { error: string } | { zoneId: string; miles: number; address: string }

const METRO_LABELS: Record<WorkZoneMetro, string> = {
  nyc: 'New York metro',
  sf: 'Bay Area',
  la: 'Los Angeles metro',
  seattle: 'Seattle metro',
}

interface WorkHubPickerProps {
  zones: WorkZone[]
  value: string | null
  onChange: (id: string | null) => void
  /** Geocodes the address and snaps it to the nearest hub. */
  onAddressSubmit: (address: string) => Promise<WorkAddressResult>
}

type Option = { kind: 'address'; query: string } | { kind: 'zone'; zone: WorkZone }

function highlight(label: string, query: string) {
  const q = query.trim().toLowerCase()
  const i = q ? label.toLowerCase().indexOf(q) : -1
  if (i < 0) return label
  return (
    <>
      {label.slice(0, i)}
      <strong style={{ fontWeight: 700 }}>{label.slice(i, i + q.length)}</strong>
      {label.slice(i + q.length)}
    </>
  )
}

export default function WorkHubPicker({ zones, value, onChange, onAddressSubmit }: WorkHubPickerProps) {
  const listId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const [editing, setEditing] = useState(false)
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [focused, setFocused] = useState(false)
  const [activeIdx, setActiveIdx] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [snappedFrom, setSnappedFrom] = useState<{ zoneId: string; address: string; miles: number } | null>(null)

  const selected = zones.find((z) => z.id === value) ?? null
  const showSearch = !selected || editing

  const options = useMemo<Option[]>(() => {
    const q = query.trim().toLowerCase()
    const matches = zones.filter((z) => !q || z.label.toLowerCase().includes(q))
    const opts: Option[] = matches.map((zone) => ({ kind: 'zone', zone }))
    // Offer an address lookup after any hub matches, unless the text is exactly a hub name.
    if (q.length >= 3 && !(matches.length === 1 && matches[0].label.toLowerCase() === q)) {
      opts.push({ kind: 'address', query: query.trim() })
    }
    return opts
  }, [zones, query])

  useEffect(() => { setActiveIdx(0) }, [query])

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false)
        if (selected) setEditing(false)
      }
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open, selected])

  const finish = () => {
    setQuery('')
    setOpen(false)
    setEditing(false)
    setError(null)
    inputRef.current?.blur()
  }

  const choose = async (opt: Option) => {
    if (opt.kind === 'zone') {
      setSnappedFrom(null)
      onChange(opt.zone.id)
      finish()
      return
    }
    setBusy(true)
    setError(null)
    setOpen(false)
    const res = await onAddressSubmit(opt.query)
    setBusy(false)
    if ('error' in res) {
      setError(res.error)
      return
    }
    setSnappedFrom({ zoneId: res.zoneId, address: res.address, miles: res.miles })
    finish()
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActiveIdx((i) => Math.min(i + 1, options.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const opt = options[activeIdx]
      if (opt && !busy) choose(opt)
    } else if (e.key === 'Escape') {
      if (open) setOpen(false)
      else if (selected) finish()
    }
  }

  if (!showSearch && selected) {
    const snapped = snappedFrom?.zoneId === selected.id ? snappedFrom : null
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '6px 6px 6px 8px',
          borderRadius: 8,
          border: '1px solid var(--hf-border)',
          background: 'var(--hf-card-bg)',
          boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
          marginBottom: 10,
        }}
      >
        <div
          aria-hidden
          style={{
            width: 28, height: 28, borderRadius: 6, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--tr-accent-50)', color: 'var(--hf-primary-1)',
          }}
        >
          <Briefcase size={14} strokeWidth={2} />
        </div>
        <button
          type="button"
          onClick={() => { setEditing(true); setOpen(true); requestAnimationFrame(() => inputRef.current?.focus()) }}
          style={{ flex: 1, minWidth: 0, textAlign: 'left', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
          aria-label={`Work hub: ${selected.label}. Change`}
        >
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--hf-text-primary)', lineHeight: 1.3 }}>{selected.label}</div>
          <div style={{ fontSize: 11, color: 'var(--hf-text-secondary)', lineHeight: 1.35, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {snapped
              ? `Nearest hub to ${snapped.address} · ${snapped.miles < 0.1 ? 'under 0.1' : snapped.miles.toFixed(1)} mi away`
              : `${METRO_LABELS[selected.metro]} · tap to change`}
          </div>
        </button>
        <button
          type="button"
          onClick={() => { setSnappedFrom(null); onChange(null) }}
          aria-label="Clear work hub"
          style={{
            width: 24, height: 24, borderRadius: 999, flexShrink: 0, border: 'none', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--hf-hover-bg)', color: 'var(--hf-text-secondary)',
          }}
        >
          <X size={13} strokeWidth={2.25} />
        </button>
      </div>
    )
  }

  const activeOption = open ? options[activeIdx] : undefined
  const optionId = (i: number) => `${listId}-opt-${i}`

  return (
    <div ref={rootRef} style={{ position: 'relative', marginBottom: 10 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          height: 36,
          padding: '0 10px',
          borderRadius: 8,
          background: 'var(--hf-card-bg)',
          border: `1px solid ${focused ? 'var(--hf-text-primary)' : 'var(--hf-border)'}`,
          boxShadow: focused ? '0 1px 6px rgba(0,0,0,0.08)' : 'none',
          transition: 'box-shadow 150ms ease, border-color 150ms ease',
        }}
      >
        {busy
          ? <Loader2 size={15} className="animate-spin" style={{ color: 'var(--hf-primary-1)', flexShrink: 0 }} aria-hidden />
          : <Search size={15} strokeWidth={2.25} style={{ color: 'var(--hf-text-primary)', flexShrink: 0 }} aria-hidden />}
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-label="Where do you work?"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={activeOption ? optionId(activeIdx) : undefined}
          value={query}
          disabled={busy}
          placeholder={busy ? 'Finding your nearest hub…' : 'Where do you work?'}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); setError(null) }}
          onFocus={() => { setFocused(true); setOpen(true) }}
          onBlur={() => setFocused(false)}
          onKeyDown={onKeyDown}
          // 16px on phones avoids iOS focus zoom; 13px elsewhere to match the app's inputs.
          className="text-base sm:text-[13px]"
          style={{
            flex: 1, minWidth: 0, height: '100%', border: 'none', outline: 'none', background: 'transparent',
            color: 'var(--hf-text-primary)',
          }}
        />
        {editing && selected && (
          <button
            type="button"
            onClick={finish}
            style={{ fontSize: 11, fontWeight: 600, color: 'var(--hf-text-secondary)', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
          >
            Cancel
          </button>
        )}
      </div>

      {open && options.length > 0 && (
        <ul
          id={listId}
          role="listbox"
          style={{
            position: 'absolute', top: 'calc(100% + 6px)', left: 0, right: 0, zIndex: 20,
            margin: 0, padding: 4, listStyle: 'none',
            maxHeight: 260, overflowY: 'auto',
            borderRadius: 12, background: 'var(--hf-card-bg)',
            border: '1px solid var(--hf-border)',
            boxShadow: 'var(--hf-card-shadow-sm)',
          }}
        >
          {!query.trim() && (
            <li aria-hidden style={{ padding: '6px 8px 4px', fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--hf-text-tertiary)' }}>
              Job hubs
            </li>
          )}
          {options.map((opt, i) => {
            const active = i === activeIdx
            const isAddress = opt.kind === 'address'
            return (
              <li
                key={isAddress ? '__address' : opt.zone.id}
                id={optionId(i)}
                role="option"
                aria-selected={active}
                onMouseEnter={() => setActiveIdx(i)}
                onMouseDown={(e) => { e.preventDefault(); choose(opt) }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '6px 8px', borderRadius: 8, cursor: 'pointer',
                  background: active ? 'var(--hf-hover-bg)' : 'transparent',
                }}
              >
                <div
                  aria-hidden
                  style={{
                    width: 28, height: 28, borderRadius: 6, flexShrink: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: isAddress ? 'var(--tr-accent-50)' : 'var(--hf-bg-subtle)',
                    color: isAddress ? 'var(--hf-primary-1)' : 'var(--hf-text-secondary)',
                    border: '1px solid var(--hf-border)',
                  }}
                >
                  {isAddress ? <MapPin size={14} /> : <Building2 size={14} />}
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, color: 'var(--hf-text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {isAddress ? <>Use &ldquo;{opt.query}&rdquo;</> : highlight(opt.zone.label, query)}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--hf-text-secondary)' }}>
                    {isAddress ? 'Snap this address to the nearest job hub' : METRO_LABELS[opt.zone.metro]}
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {error && (
        <div role="alert" style={{ marginTop: 4, paddingLeft: 2, fontSize: 11, color: 'var(--hf-danger)' }}>{error}</div>
      )}
    </div>
  )
}
