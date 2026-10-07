'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Link from 'next/link'
import { Briefcase, Loader2, Trash2, Users, Wallet, X } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import WorkHubPicker, { type WorkAddressResult } from '@/components/catalog/WorkHubPicker'
import PeopleYouKnowPicker from '@/components/catalog/PeopleYouKnowPicker'
import { WORK_ZONES, snapToWorkZone } from '@/lib/workZones'
import { savePeople } from '@/lib/socialConnections'
import {
  fetchProfile,
  readLocalProfile,
  saveProfile,
  type CommuteMode,
  type UserProfile,
} from '@/lib/userProfile'

type SaveState = 'idle' | 'local' | 'saving' | 'saved' | 'error'

interface HomeOption {
  name: string
  sub: string
}

/** Catalog place names for the current-home picker, fetched once on first use. */
let homeOptionsCache: HomeOption[] | null = null
async function loadHomeOptions(): Promise<HomeOption[]> {
  if (homeOptionsCache) return homeOptionsCache
  try {
    const res = await fetch('/api/catalog-map?metro=all')
    const json = await res.json()
    const places: any[] = Array.isArray(json?.places) ? json.places : []
    homeOptionsCache = places
      .map((p) => ({
        name: String(p?.catalog?.name ?? ''),
        sub: [p?.catalog?.county_borough, p?.catalog?.state_abbr].filter(Boolean).join(', '),
      }))
      .filter((o) => o.name)
    return homeOptionsCache
  } catch {
    return []
  }
}

/**
 * Mirrors a profile change into the explorer's local settings so the explorer, search and results
 * pages see it immediately, signed in or not.
 */
function persistLocal(patch: Partial<UserProfile>) {
  try {
    const opts = JSON.parse(localStorage.getItem('homefit_search_options') ?? 'null') ?? {}
    if ('household_income' in patch) opts.household_income = patch.household_income ?? null
    if ('current_home' in patch) {
      opts.current_home_match = patch.current_home?.name ?? ''
      opts.current_home_monthly_cost = patch.current_home?.monthly_cost ?? null
    }
    if ('commute_mode' in patch) opts.commute_mode = patch.commute_mode ?? null
    if ('office_days' in patch) opts.office_days = patch.office_days ?? null
    if ('work_zone_id' in patch) opts.filters = { ...(opts.filters ?? {}), workZoneId: patch.work_zone_id ?? null }
    localStorage.setItem('homefit_search_options', JSON.stringify(opts))
  } catch { /* private window or full storage: the account copy still saves */ }
  if (patch.people) savePeople(patch.people)
}

function digitsToNumber(raw: string): number | null {
  const n = parseInt(raw.replace(/[^0-9]/g, ''), 10)
  return Number.isFinite(n) && n > 0 ? n : null
}

const INPUT_CLASS =
  'min-h-[44px] w-full rounded-lg border border-[var(--hf-border)] bg-white px-3 py-2.5 text-base text-[var(--hf-text-primary)] ' +
  'placeholder:text-[var(--hf-text-tertiary)] focus:border-[var(--hf-text-primary)] focus:outline-none sm:text-sm'

function Chip({
  active,
  onClick,
  className = '',
  children,
}: {
  active: boolean
  onClick: () => void
  className?: string
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={
        'min-h-[44px] rounded-full px-4 text-sm font-semibold transition-colors sm:min-h-[36px] ' + className + ' ' +
        (active
          ? 'bg-[var(--hf-primary-1)] text-white'
          : 'border border-[var(--hf-border)] bg-[var(--hf-hover-bg)] text-[var(--hf-text-secondary)] hover:text-[var(--hf-text-primary)]')
      }
    >
      {children}
    </button>
  )
}

function Section({
  icon: Icon,
  title,
  blurb,
  children,
}: {
  icon: typeof Wallet
  title: string
  blurb: string
  children: React.ReactNode
}) {
  return (
    <section className="hf-panel !p-4 sm:!p-6">
      <div className="mb-4 flex items-start gap-3">
        <div
          aria-hidden
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-[var(--tr-accent-50)] text-[var(--hf-primary-1)]"
        >
          <Icon size={18} strokeWidth={2} />
        </div>
        <div className="min-w-0">
          <h2 className="m-0 text-base font-bold text-[var(--hf-text-primary)]">{title}</h2>
          <p className="m-0 mt-0.5 text-xs leading-snug text-[var(--hf-text-secondary)]">{blurb}</p>
        </div>
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  )
}

function Label({ htmlFor, children }: { htmlFor?: string; children: React.ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-xs font-semibold text-[var(--hf-text-primary)]">
      {children}
    </label>
  )
}

export default function ProfilePage() {
  const { user, loading: authLoading, openAuthModal } = useAuth()
  const [profile, setProfile] = useState<Partial<UserProfile>>({})
  const [saveState, setSaveState] = useState<SaveState>('idle')

  const [incomeInput, setIncomeInput] = useState('')
  const [costInput, setCostInput] = useState('')
  const [homeQuery, setHomeQuery] = useState('')
  const [homeOpen, setHomeOpen] = useState(false)
  const [homeOptions, setHomeOptions] = useState<HomeOption[]>([])
  const homeBoxRef = useRef<HTMLDivElement>(null)

  const pending = useRef<Partial<UserProfile>>({})
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const userRef = useRef(user)
  userRef.current = user

  const syncInputs = useCallback((p: Partial<UserProfile>) => {
    setIncomeInput(p.household_income ? p.household_income.toLocaleString('en-US') : '')
    setCostInput(p.current_home?.monthly_cost ? p.current_home.monthly_cost.toLocaleString('en-US') : '')
    setHomeQuery(p.current_home?.name ?? '')
  }, [])

  // Local settings first so the page isn't empty, then the account profile over them.
  useEffect(() => {
    const local = readLocalProfile()
    setProfile(local)
    syncInputs(local)
  }, [syncInputs])

  useEffect(() => {
    if (!user) return
    let cancelled = false
    fetchProfile().then((remote) => {
      if (cancelled || !remote) return
      setProfile((prev) => {
        const merged = { ...prev, ...remote }
        syncInputs(merged)
        return merged
      })
    })
    return () => { cancelled = true }
  }, [user, syncInputs])

  const flush = useCallback(async () => {
    const body = pending.current
    pending.current = {}
    if (Object.keys(body).length === 0) return
    const ok = await saveProfile(body)
    setSaveState(ok ? 'saved' : 'error')
  }, [])

  // Don't lose an edit made just before navigating away.
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current)
    if (userRef.current && Object.keys(pending.current).length) void saveProfile(pending.current)
  }, [])

  const update = useCallback((patch: Partial<UserProfile>) => {
    setProfile((p) => ({ ...p, ...patch }))
    persistLocal(patch)
    if (!userRef.current) {
      setSaveState('local')
      return
    }
    pending.current = { ...pending.current, ...patch }
    setSaveState('saving')
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(flush, 800)
  }, [flush])

  useEffect(() => {
    if (!homeOpen) return
    const onDown = (e: MouseEvent) => {
      if (homeBoxRef.current && !homeBoxRef.current.contains(e.target as Node)) setHomeOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [homeOpen])

  const homeMatches = useMemo(() => {
    const q = homeQuery.trim().toLowerCase()
    if (q.length < 2) return []
    return homeOptions
      .filter((o) => o.name.toLowerCase().includes(q) || o.sub.toLowerCase().includes(q))
      .slice(0, 8)
  }, [homeOptions, homeQuery])

  const commitIncome = () => {
    const n = digitsToNumber(incomeInput)
    setIncomeInput(n ? n.toLocaleString('en-US') : '')
    if (n !== (profile.household_income ?? null)) update({ household_income: n })
  }

  const commitCost = () => {
    const n = digitsToNumber(costInput)
    const valid = n !== null && n >= 100 ? n : null
    setCostInput(valid ? valid.toLocaleString('en-US') : '')
    if (profile.current_home && valid !== profile.current_home.monthly_cost) {
      update({ current_home: { name: profile.current_home.name, monthly_cost: valid } })
    }
  }

  const chooseHome = (o: HomeOption) => {
    setHomeQuery(o.name)
    setHomeOpen(false)
    update({ current_home: { name: o.name, monthly_cost: profile.current_home?.monthly_cost ?? null } })
  }

  const clearHome = () => {
    setHomeQuery('')
    setCostInput('')
    setHomeOpen(false)
    update({ current_home: null })
  }

  const submitWorkAddress = useCallback(async (address: string): Promise<WorkAddressResult> => {
    try {
      const res = await fetch(`/api/geocode?location=${encodeURIComponent(address)}`)
      const data = await res.json().catch(() => ({}))
      if (!res.ok || typeof data?.lat !== 'number') return { error: data?.detail || "We couldn't find that address." }
      const snapped = snapToWorkZone(data.lat, data.lon, WORK_ZONES)
      if (!snapped) return { error: "That address isn't near a job hub we have commute times for yet." }
      update({ work_zone_id: snapped.zone.id })
      return { zoneId: snapped.zone.id, miles: snapped.miles, address }
    } catch {
      return { error: 'Location service is temporarily unavailable.' }
    }
  }, [update])

  const clearAll = () => {
    if (!window.confirm('Clear everything in your profile? Your scores go back to area averages.')) return
    update({ household_income: null, current_home: null, work_zone_id: null, commute_mode: null, office_days: null, people: [] })
    setIncomeInput('')
    setCostInput('')
    setHomeQuery('')
  }

  const costShare =
    profile.household_income && profile.current_home?.monthly_cost
      ? Math.round(((profile.current_home.monthly_cost * 12) / profile.household_income) * 100)
      : null

  const mode: CommuteMode | null = profile.commute_mode ?? null
  const days = profile.office_days ?? null
  const hasAnything = Boolean(
    profile.household_income || profile.current_home || profile.work_zone_id ||
    profile.commute_mode || profile.office_days !== undefined && profile.office_days !== null || profile.people?.length
  )

  const status =
    saveState === 'saving' ? { text: 'Saving…', busy: true }
    : saveState === 'saved' ? { text: 'Saved to your account', busy: false }
    : saveState === 'error' ? { text: "Couldn't save to your account. Kept on this device.", busy: false }
    : saveState === 'local' ? { text: 'Saved on this device', busy: false }
    : null

  return (
    <main className="hf-page hf-page-no-hero">
      <div className="mx-auto w-full max-w-[720px] px-4 pb-24 pt-6 sm:px-6 sm:pt-10">
        <header className="mb-6">
          <h1 className="m-0 text-3xl text-[var(--hf-text-primary)] sm:text-4xl" style={{ fontFamily: 'var(--font-display)' }}>
            Your profile
          </h1>
          <p className="m-0 mt-2 text-sm leading-relaxed text-[var(--hf-text-secondary)]">
            Tell us a little about your life and we&rsquo;ll adjust every score to fit it. Everything is optional,
            and anything you leave blank falls back to area averages.
          </p>
          <div className="mt-3 flex min-h-[24px] flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--hf-text-tertiary)]" aria-live="polite">
            {status && (
              <span className="inline-flex items-center gap-1.5">
                {status.busy && <Loader2 size={12} className="animate-spin" aria-hidden />}
                {status.text}
              </span>
            )}
            {!authLoading && !user && (
              <button
                type="button"
                onClick={() => openAuthModal('signin')}
                className="font-semibold text-[var(--hf-primary-1)] underline underline-offset-2"
              >
                Sign in to keep this across devices
              </button>
            )}
          </div>
        </header>

        <div className="space-y-4">
          <Section
            icon={Wallet}
            title="Income and home"
            blurb="Used to judge housing affordability against what you can actually afford."
          >
            <div>
              <Label htmlFor="profile-income">Annual household income</Label>
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-[var(--hf-text-secondary)]">$</span>
                <input
                  id="profile-income"
                  type="text"
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="e.g. 120,000"
                  value={incomeInput}
                  onChange={(e) => setIncomeInput(e.target.value)}
                  onBlur={commitIncome}
                  onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }}
                  className={INPUT_CLASS + ' pl-7'}
                />
              </div>
            </div>

            <div ref={homeBoxRef} className="relative">
              <Label htmlFor="profile-home">Where you live now</Label>
              <div className="relative">
                <input
                  id="profile-home"
                  type="text"
                  autoComplete="off"
                  placeholder="Search a neighborhood we score"
                  value={homeQuery}
                  onChange={(e) => { setHomeQuery(e.target.value); setHomeOpen(true) }}
                  onFocus={() => {
                    setHomeOpen(true)
                    if (!homeOptions.length) void loadHomeOptions().then(setHomeOptions)
                  }}
                  className={INPUT_CLASS + (profile.current_home ? ' pr-10' : '')}
                  role="combobox"
                  aria-expanded={homeOpen && homeMatches.length > 0}
                  aria-controls="profile-home-list"
                  aria-autocomplete="list"
                />
                {profile.current_home && (
                  <button
                    type="button"
                    onClick={clearHome}
                    aria-label="Clear current home"
                    className="absolute right-1.5 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full text-[var(--hf-text-tertiary)] hover:bg-[var(--hf-hover-bg)] hover:text-[var(--hf-text-secondary)]"
                  >
                    <X size={15} />
                  </button>
                )}
              </div>
              {homeOpen && homeMatches.length > 0 && (
                <ul
                  id="profile-home-list"
                  role="listbox"
                  className="absolute left-0 right-0 top-full z-20 mt-1.5 max-h-64 overflow-y-auto rounded-xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] p-1 shadow-[var(--hf-card-shadow-sm)]"
                >
                  {homeMatches.map((o) => (
                    <li key={`${o.name}|${o.sub}`} role="option" aria-selected={profile.current_home?.name === o.name}>
                      <button
                        type="button"
                        onMouseDown={(e) => { e.preventDefault(); chooseHome(o) }}
                        onClick={() => chooseHome(o)}
                        className="flex min-h-[44px] w-full flex-col justify-center rounded-lg px-3 py-1.5 text-left hover:bg-[var(--hf-hover-bg)]"
                      >
                        <span className="text-sm font-medium text-[var(--hf-text-primary)]">{o.name}</span>
                        {o.sub && <span className="text-xs text-[var(--hf-text-tertiary)]">{o.sub}</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {profile.current_home && (
              <div>
                <Label htmlFor="profile-cost">Your monthly housing cost</Label>
                <div className="relative">
                  <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-[var(--hf-text-secondary)]">$</span>
                  <input
                    id="profile-cost"
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    placeholder="Rent, or mortgage plus tax"
                    value={costInput}
                    onChange={(e) => setCostInput(e.target.value)}
                    onBlur={commitCost}
                    onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }}
                    className={INPUT_CLASS + ' pl-7'}
                  />
                </div>
                <p className="m-0 mt-1.5 text-xs text-[var(--hf-text-secondary)]">
                  {costShare !== null
                    ? `That's about ${costShare}% of your income. Only this neighborhood uses your real cost; every other place uses its area median.`
                    : 'Add your income above to see this as a share of what you earn. Only this neighborhood uses your real cost.'}
                </p>
              </div>
            )}
          </Section>

          <Section
            icon={Briefcase}
            title="Work and commute"
            blurb="Replaces the area-average commute with your own trip to work."
          >
            <div>
              <Label>Where do you work?</Label>
              <WorkHubPicker
                zones={WORK_ZONES}
                value={profile.work_zone_id ?? null}
                onChange={(id) => update({ work_zone_id: id })}
                onAddressSubmit={submitWorkAddress}
              />
            </div>

            <div>
              <Label>How do you get there?</Label>
              <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
                <Chip active={mode === null} onClick={() => update({ commute_mode: null })}>Fastest</Chip>
                <Chip active={mode === 'auto'} onClick={() => update({ commute_mode: mode === 'auto' ? null : 'auto' })}>Drive</Chip>
                <Chip active={mode === 'transit'} onClick={() => update({ commute_mode: mode === 'transit' ? null : 'transit' })}>Transit</Chip>
                <Chip active={mode === 'active'} onClick={() => update({ commute_mode: mode === 'active' ? null : 'active' })}>Walk or bike</Chip>
              </div>
              {mode === 'active' && (
                <p className="m-0 mt-1.5 text-xs text-[var(--hf-text-secondary)]">
                  We don&rsquo;t have walk or bike routing yet, so the area-average commute is used.
                </p>
              )}
            </div>

            <div>
              <Label>Days per week in the office</Label>
              <div className="grid grid-cols-7 gap-2 sm:flex sm:flex-wrap">
                {[0, 1, 2, 3, 4, 5].map((d) => (
                  <Chip
                    key={d}
                    active={days === d}
                    onClick={() => update({ office_days: days === d ? null : d })}
                    className={d === 0 ? 'col-span-2' : '!px-0 sm:!px-4'}
                  >
                    {d === 0 ? 'Remote' : d}
                  </Chip>
                ))}
              </div>
              <p className="m-0 mt-1.5 text-xs text-[var(--hf-text-secondary)]">
                Fewer office days count your commute less. Fully remote ignores it.
              </p>
            </div>
          </Section>

          <Section
            icon={Users}
            title="People you want to live near"
            blurb="Family and friends. Places closer to them score higher on social connection."
          >
            <PeopleYouKnowPicker people={profile.people ?? []} onPeopleChange={(next) => update({ people: next })} />
          </Section>
        </div>

        <footer className="mt-8 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Link
            href="/catalog"
            className="hf-btn-primary inline-flex min-h-[44px] items-center justify-center !px-6 !py-3 text-center no-underline"
          >
            See your scores
          </Link>
          {hasAnything && (
            <button
              type="button"
              onClick={clearAll}
              className="inline-flex min-h-[44px] items-center justify-center gap-1.5 rounded-lg px-3 text-sm font-semibold text-[var(--hf-text-secondary)] hover:bg-[var(--hf-hover-bg)] hover:text-[var(--hf-text-primary)]"
            >
              <Trash2 size={14} aria-hidden /> Clear my profile
            </button>
          )}
        </footer>
      </div>
    </main>
  )
}
