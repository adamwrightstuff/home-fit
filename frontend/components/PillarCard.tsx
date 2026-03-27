'use client'

import { useState } from 'react'
import { LivabilityPillar } from '@/types/api'
import {
  PILLAR_META,
  getScoreBandLabel,
  getScoreBandColor,
  getScoreBandBackground,
  getPillarFailureType,
  PILLAR_LONG_DESCRIPTIONS,
  isLongevityPillar,
  LONGEVITY_COPY,
  type PillarKey,
} from '@/lib/pillars'
import {
  PILLAR_DETAILS_SPEC,
  getPillarValue,
  getPillarString,
  formatPercent,
  resolveQualitative,
  type DetailMetric,
  type DetailMetricStatic,
} from '@/lib/pillarDetailsSpec'
import { getPillarNarrative } from '@/lib/pillarNarratives'

interface PillarCardProps {
  pillar_key: PillarKey
  pillar: LivabilityPillar
  /** Human-readable place label (e.g. "Carroll Gardens, Brooklyn") for location-specific narratives. */
  placeLabel?: string
  /** When true, render this card in a loading/skeleton state. */
  loading?: boolean
  /** When provided, Rerun button is shown for fallback/failed pillars. */
  onRerun?: (pillarKey: PillarKey) => void
  /** When true, Rerun is disabled (e.g. full run or another rerun in progress). */
  rerunDisabled?: boolean
  /** When provided, show "Rescore this pillar" in expanded details (below data breakdown). */
  onRescorePillar?: (pillarKey: PillarKey) => void
  /** When true, rescore link shows "Rescoring…" and is disabled. */
  rescoring?: boolean
  /** Neighborhood Amenities only: whether chain businesses are included. */
  includeChainsValue?: boolean
  /** Neighborhood Amenities only: toggle include_chains and (optionally) rescore. */
  onIncludeChainsChange?: (next: boolean) => void
  /** Natural Beauty only: preference profile applied when scoring. */
  naturalBeautyPreference?: string[] | null
  /** Natural Beauty only: when provided, show scenery preference chips and call with new value (can trigger rescore). */
  onNaturalBeautyPreferenceChange?: (preference: string[] | null) => void
  /** Built Beauty only: character preference applied when scoring. */
  builtCharacterPreference?: string | null
  /** Built Beauty only: density preference applied when scoring. */
  builtDensityPreference?: string | null
  /** Current importance for this pillar (for inline weight editing on Results). */
  importanceLevel?: 'None' | 'Low' | 'Medium' | 'High'
  /** When provided, show None/Low/Medium/High toggle and call with new level (client-side reweight). */
  onImportanceChange?: (level: 'None' | 'Low' | 'Medium' | 'High') => void
}

/** Natural Beauty scenery preference options (max 2; "Any" clears selection). */
const NATURAL_BEAUTY_PREFERENCE_CHIPS: Array<{ value: string | null; label: string }> = [
  { value: null, label: 'Any' },
  { value: 'mountains', label: 'Mountains' },
  { value: 'ocean', label: 'Ocean' },
  { value: 'lakes_rivers', label: 'Lakes & rivers' },
  { value: 'canopy', label: 'Greenery' },
]

function isRecord(value: unknown): value is Record<string, any> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return 'N/A'
  return n % 1 === 0 ? n.toString() : n.toFixed(2)
}

function formatValue(value: any, depth: number = 0): string {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'number') return formatNumber(value)
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.length ? value.map((v) => String(v)).join(', ') : '—'

  if (isRecord(value)) {
    // Common pattern in API: { count, types } for tier summaries
    const count = typeof value.count === 'number' ? value.count : null
    const types = Array.isArray(value.types) ? value.types : null
    if (count !== null && types) {
      const typeStr = types.length ? types.join(', ') : '—'
      return `${count} (${typeStr})`
    }

    // For small objects, render key=value pairs (avoid [object Object])
    if (depth < 2) {
      const entries = Object.entries(value)
        .filter(([, v]) => typeof v !== 'object' || v === null)
        .slice(0, 6)
      if (entries.length) {
        return entries.map(([k, v]) => `${k.replace(/_/g, ' ')}: ${formatValue(v, depth + 1)}`).join(', ')
      }
    }

    return '—'
  }

  return String(value)
}

/** Format one spec metric value for display. Returns null if metric should be omitted (no value). */
function formatSpecMetricValue(
  pillar: Record<string, unknown>,
  metric: DetailMetric,
  staticTexts: { local_vs_chains?: string }
): string | null {
  if (metric.format === 'static') {
    const key = (metric as DetailMetricStatic).textKey
    const t = staticTexts[key as keyof typeof staticTexts]
    return t ?? null
  }
  const path = 'path' in metric ? metric.path : ''
  const num = getPillarValue(pillar, path)
  const str = getPillarString(pillar, path)

  switch (metric.format) {
    case 'percent':
      if (num === undefined) return null
      return formatPercent(num, metric.max)
    case 'count':
      if (num === undefined && (str === undefined || str === '')) return null
      const n = num ?? (str !== undefined && str !== '' ? parseFloat(str) : NaN)
      if (!Number.isFinite(n)) return null
      const suffix = metric.suffix ?? ''
      return `${Math.round(n)}${suffix}`
    case 'distance':
      if (num === undefined && (str === undefined || str === '')) return null
      const d = num ?? (str !== undefined ? parseFloat(str) : NaN)
      if (!Number.isFinite(d)) return str ?? null
      return `${d.toFixed(1)} km`
    case 'qualitative':
      if (num !== undefined) return resolveQualitative(num, metric.bands, metric.valueLabels)
      if (str !== undefined && str !== '') {
        if (metric.valueLabels && metric.valueLabels[str]) return metric.valueLabels[str]
        return str
      }
      return null
    case 'text':
      if (str !== undefined && str !== '') return str
      return null
    default:
      return null
  }
}

const METRIC_EXPLAINERS: Record<string, string> = {
  'natural_beauty:Tree score': 'How much of the nearby area is covered by trees and greenery.',
  'natural_beauty:Neighborhood canopy': 'Share of your neighborhood area with tree cover.',
  'natural_beauty:Local canopy': 'Tree cover close to your home.',
  'natural_beauty:Extended canopy': 'Tree cover in the wider surroundings.',
  'active_outdoors:Daily urban outdoors': 'Parks and everyday green spaces for short walks and play.',
  'active_outdoors:Wild adventure': 'Trails and wilder areas for hiking and exploring.',
  'active_outdoors:Waterfront lifestyle': 'Nearby lakes, rivers, or coasts you can enjoy.',
  'neighborhood_amenities:Home walkability': 'How many daily needs you can reach on foot from home.',
  'neighborhood_amenities:Daily needs nearby': 'Rough count of shops and services within about a 10–15 minute walk.',
  'neighborhood_amenities:Town center & vibrancy': 'Strength of the nearest main street or town center.',
  'neighborhood_amenities:Local vs chains': 'Whether the score focuses on local spots or includes chain businesses.',
  'built_beauty:Architecture diversity': 'Variety of building types and styles nearby.',
  'built_beauty:Street character': 'How human-scale and interesting the surrounding streets feel.',
  'healthcare_access:Hospital access': 'Number of hospitals nearby and how far they are.',
  'healthcare_access:Primary care': 'Access to everyday doctors and clinics.',
  'healthcare_access:Specialized care': 'Access to specialists for specific conditions.',
  'healthcare_access:Emergency services': 'Access to emergency rooms and urgent care.',
  'healthcare_access:Pharmacies': 'Nearby places to fill prescriptions.',
  'healthcare_access:Facilities': 'Total hospitals within a reasonable drive.',
  'public_transit_access:Heavy rail': 'Access to subway or commuter rail within reach.',
  'public_transit_access:Light rail': 'Access to trams or light rail lines.',
  'public_transit_access:Bus': 'Availability of useful bus routes nearby.',
  'public_transit_access:Nearest heavy rail': 'Distance to the closest major rail stop.',
  'public_transit_access:Connectivity': 'How well that rail line connects to the wider region.',
  'air_travel_access:Nearest airport': 'Main airport you’re most likely to use.',
  'air_travel_access:Distance': 'Travel distance from this place to that airport.',
  'air_travel_access:Airports within range': 'Major airports you can reasonably reach from here.',
  'economic_security:Job market fit': 'Overall strength of the local job market for this kind of work.',
  'economic_security:Area': 'Broader U.S. region this place is compared against.',
  'quality_education:Average school rating': 'Average quality of nearby schools on a 0–10 scale.',
  'quality_education:Schools rated': 'How many nearby schools have rating data.',
  'quality_education:Excellent schools': 'Count of top-rated schools nearby.',
  'housing_value:Local affordability': 'How manageable housing costs are relative to local incomes.',
  'housing_value:Space': 'How much room you generally get for the price.',
  'housing_value:Value efficiency': 'Overall “bang for your buck” on housing here.',
  'housing_value:Median home value': 'Typical home price in this area.',
  'climate_risk:Flood risk': 'Overall chance of flooding based on local flood zones.',
  'climate_risk:Heat exposure': 'How often this area runs hotter than is comfortable.',
  'climate_risk:Air quality': 'How often the air is clean versus polluted.',
  'climate_risk:Climate trend': 'How much climate risks here are expected to change over time.',
  'social_fabric:Civic places (OpenStreetMap)': 'Whether civic gathering places could be loaded from OpenStreetMap (libraries, community centers, etc.).',
  'social_fabric:Engagement (IRS orgs)': 'Whether IRS exempt-organization density could be compared for this tract or region.',
  'social_fabric:Engagement (turnout)': 'Whether modeled voter turnout could be applied for this tract.',
  'social_fabric:Residential stability (tract + place)': 'Blend of tract and place (CDP/incorporated) same-house rates.',
  'social_fabric:Civic places (search radius)': 'Count of non-commercial civic places within the density-based search radius.',
  'social_fabric:Civic search radius (m)': 'Search distance used for civic places based on tract density.',
  'social_fabric:Voter turnout (tract)': 'Estimated voter participation used for the engagement blend when available.',
  'diversity:Diversity score': 'Race, income, and age mix (entropy) from Census tract distributions.',
}

export default function PillarCard({
  pillar_key,
  pillar,
  placeLabel,
  loading,
  onRerun,
  rerunDisabled,
  onRescorePillar,
  rescoring,
  includeChainsValue,
  onIncludeChainsChange,
  importanceLevel,
  onImportanceChange,
  naturalBeautyPreference,
  onNaturalBeautyPreferenceChange,
  builtCharacterPreference,
  builtDensityPreference,
}: PillarCardProps) {
  const [expanded, setExpanded] = useState(false)
  const meta = PILLAR_META[pillar_key]
  const isLoading = Boolean(loading)
  const isNone = importanceLevel === 'None'
  const mutedStyle = isNone ? { color: 'var(--hf-text-secondary)', opacity: 0.85 } : undefined
  const rawSummary = pillar.summary || {}
  // Backend may send details in summary and/or breakdown; use whichever has keys so we show something.
  const rawBreakdown = pillar.breakdown || {}
  const hasSummary = isRecord(rawSummary) && Object.keys(rawSummary).length > 0
  const hasBreakdown = isRecord(rawBreakdown) && Object.keys(rawBreakdown).length > 0
  const detailsSource = hasSummary ? rawSummary : hasBreakdown ? rawBreakdown : null
  const failureType = getPillarFailureType(pillar)
  const showRerun = (failureType === 'fallback' || failureType === 'execution_error') && onRerun
  const isFailed = failureType === 'execution_error'
  const isFallback = failureType === 'fallback'
  const isIncomplete = failureType === 'incomplete'
  const isSchoolsNotScored =
    pillar_key === 'quality_education' &&
    pillar.score === 0 &&
    (pillar.data_quality as { fallback_used?: boolean; reason?: string } | undefined)?.fallback_used === true &&
    String((pillar.data_quality as { reason?: string } | undefined)?.reason ?? '').toLowerCase().includes('disabled')

  // Built Beauty: the useful metrics live under details.architectural_analysis.metrics.
  // Some summary fields are placeholders (often zeros), so override them when available.
  const builtMetrics = pillar_key === 'built_beauty' ? pillar.details?.architectural_analysis?.metrics : null
  const summary =
    pillar_key === 'built_beauty' && isRecord(builtMetrics)
      ? {
          ...rawSummary,
          height_diversity: builtMetrics.height_diversity ?? rawSummary.height_diversity,
          type_diversity: builtMetrics.type_diversity ?? rawSummary.type_diversity,
          footprint_variation: builtMetrics.footprint_variation ?? rawSummary.footprint_variation,
          built_coverage_ratio: builtMetrics.built_coverage_ratio ?? rawSummary.built_coverage_ratio,
          // Prefer the real metric from architectural_analysis.metrics.
          // (Summary values are sometimes placeholders.)
          diversity_score:
            builtMetrics.diversity_score ?? rawSummary.diversity_score ?? pillar.details?.architectural_analysis?.score,
        }
      : detailsSource ?? {}

  const locationLabel = placeLabel || 'This area'
  const pillarNarrative = getPillarNarrative(pillar_key, locationLabel, pillar as unknown as Record<string, unknown>)

  return (
    <div
      className="hf-card-sm"
      style={{ cursor: 'default' }}
    >
      {/* Top row: left = icon + name + tags; right = score + quality label */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: '0.85rem', alignItems: 'flex-start', minWidth: 0, flex: '1 1 0' }}>
          <div style={{ fontSize: '1.6rem', flexShrink: 0 }}>{meta.icon}</div>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--hf-text-primary)' }}>{meta.name}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
              {isLongevityPillar(pillar_key) && (
                <span
                  className="hf-muted"
                  title={pillarNarrative ?? LONGEVITY_COPY.tooltip}
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.45rem',
                    borderRadius: 6,
                    background: 'rgba(45, 106, 79, 0.12)',
                    color: 'var(--hf-homefit-green)',
                    border: '1px solid rgba(45, 106, 79, 0.3)',
                  }}
                >
                  Longevity
                </span>
              )}
              {isIncomplete && (
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.45rem',
                    borderRadius: 6,
                    background: '#C8B84A',
                    color: 'rgba(0,0,0,0.75)',
                    border: '1px solid #A89A3A',
                  }}
                  title="Score is based on incomplete data for this location and may not be fully accurate."
                  aria-describedby={`pillar-${pillar_key}-incomplete-desc`}
                >
                  Limited data
                  <span id={`pillar-${pillar_key}-incomplete-desc`} style={{ position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap', border: 0 }}>
                    Score is based on incomplete data for this location and may not be fully accurate.
                  </span>
                </span>
              )}
              {isFallback && !isSchoolsNotScored && (
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.45rem',
                    borderRadius: 6,
                    background: '#C8B84A',
                    color: 'rgba(0,0,0,0.75)',
                    border: '1px solid #A89A3A',
                  }}
                  title="Real data wasn't available — this score is estimated and may not reflect this location accurately."
                  aria-describedby={`pillar-${pillar_key}-fallback-desc`}
                >
                  Estimated score
                  <span id={`pillar-${pillar_key}-fallback-desc`} style={{ position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap', border: 0 }}>
                    Real data wasn&apos;t available — this score is estimated and may not reflect this location accurately.
                  </span>
                </span>
              )}
              {isSchoolsNotScored && (
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.45rem',
                    borderRadius: 6,
                    background: 'var(--hf-bg-subtle)',
                    color: 'var(--hf-text-secondary)',
                    border: '1px solid var(--hf-border)',
                  }}
                  title="School scoring was not run for this location."
                  aria-describedby={`pillar-${pillar_key}-not-scored-desc`}
                >
                  Not scored
                  <span id={`pillar-${pillar_key}-not-scored-desc`} style={{ position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap', border: 0 }}>
                    School scoring was not run for this location.
                  </span>
                </span>
              )}
              {isFailed && (
                <span
                  className="hf-muted"
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 600,
                    padding: '0.2rem 0.45rem',
                    borderRadius: 6,
                    background: 'var(--hf-bg-subtle)',
                    border: '1px solid var(--hf-border)',
                  }}
                  title="We weren't able to retrieve data for this pillar."
                  aria-describedby={`pillar-${pillar_key}-failed-desc`}
                >
                  Data unavailable
                  <span id={`pillar-${pillar_key}-failed-desc`} style={{ position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap', border: 0 }}>
                    We weren&apos;t able to retrieve data for this pillar.
                  </span>
                </span>
              )}
              {showRerun && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    onRerun?.(pillar_key)
                  }}
                  disabled={rerunDisabled}
                  aria-label="Rerun this pillar"
                  className="hf-btn-primary"
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    padding: '0.35rem 0.6rem',
                    minHeight: 44,
                    minWidth: 44,
                    borderRadius: 6,
                    cursor: rerunDisabled ? 'not-allowed' : 'pointer',
                    opacity: rerunDisabled ? 0.6 : 1,
                  }}
                >
                  Rerun
                </button>
              )}
            </div>
            <div className="hf-muted" style={{ fontSize: '0.95rem', marginTop: '0.5rem', lineHeight: 1.4 }}>
              {meta.description}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', flexShrink: 0 }}>
          <span
            style={{
              display: 'inline-flex',
              flexDirection: 'column',
              alignItems: 'flex-end',
              fontWeight: 800,
              fontSize: '1.75rem',
              lineHeight: 1.2,
              color: isLoading ? 'var(--hf-text-secondary)' : isFailed ? 'var(--hf-text-secondary)' : getScoreBandColor(pillar.score),
              ...(isNone ? { color: 'var(--hf-text-secondary)', opacity: 0.85 } : {}),
            }}
          >
            {isLoading ? '—' : isFailed ? '?' : <>{isFallback && !isSchoolsNotScored && <span style={{ opacity: 0.9 }}>~</span>}{pillar.score.toFixed(0)}</>}
          </span>
          {!isFailed && !isLoading && (
            <span
              style={{
                fontSize: '0.8rem',
                fontWeight: 600,
                marginTop: '0.2rem',
                color: getScoreBandColor(pillar.score),
                ...(isNone ? { color: 'var(--hf-text-secondary)', opacity: 0.85 } : {}),
              }}
            >
              {getScoreBandLabel(pillar.score)}
            </span>
          )}
          {isLoading && (
            <span className="hf-muted" style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
              Computing…
            </span>
          )}
        </div>
      </div>

      {/* Importance: pill-style Low / Medium / High (and None when editable) */}
      {onImportanceChange != null ? (
        <div style={{ marginTop: '1rem' }}>
          <div className="hf-label" style={{ marginBottom: '0.5rem' }}>Importance</div>
          <div style={{ display: 'inline-flex', flexWrap: 'wrap', gap: '0.35rem' }}>
            {(['None', 'Low', 'Medium', 'High'] as const).map((level) => (
              <button
                key={level}
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  onImportanceChange(level)
                }}
                style={{
                  padding: '0.4rem 0.75rem',
                  minHeight: 40,
                  fontSize: '0.9rem',
                  fontWeight: importanceLevel === level ? 700 : 500,
                  borderRadius: 999,
                  border: `1px solid ${importanceLevel === level ? 'var(--hf-primary-1)' : 'var(--hf-border)'}`,
                  background: importanceLevel === level ? 'var(--hf-primary-1)' : 'var(--hf-bg-subtle)',
                  color: importanceLevel === level ? 'white' : 'var(--hf-text-secondary)',
                  cursor: 'pointer',
                }}
              >
                {level}
              </button>
            ))}
          </div>
          {/* Status bar: green fill representing weight (or score) */}
          <div
            style={{
              marginTop: '0.6rem',
              height: 6,
              borderRadius: 999,
              background: 'var(--hf-border)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${Math.min(100, (pillar.weight ?? 0))}%`,
                borderRadius: 999,
                background: 'var(--hf-homefit-green)',
                transition: 'width 0.25s ease',
              }}
            />
          </div>
        </div>
      ) : null}

      {/* Metrics: Weight, Contribution, Confidence */}
      <div
        style={{
          marginTop: '1rem',
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '0.75rem 1rem',
          alignItems: 'baseline',
        }}
      >
        <div>
          <div className="hf-label" style={{ fontSize: '0.8rem', marginBottom: '0.2rem' }}>Weight</div>
          <div style={{ fontWeight: 800, color: isNone ? 'var(--hf-text-secondary)' : 'var(--hf-text-primary)', fontSize: '1rem', opacity: isNone ? 0.85 : 1 }}>
            {Number(pillar.weight).toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="hf-label" style={{ fontSize: '0.8rem', marginBottom: '0.2rem' }}>Contribution</div>
          <div style={{ fontWeight: 800, color: isNone ? 'var(--hf-text-secondary)' : 'var(--hf-text-primary)', fontSize: '1rem', opacity: isNone ? 0.85 : 1 }}>
            {pillar.contribution.toFixed(1)}
          </div>
        </div>
        <div>
          <div className="hf-label" style={{ fontSize: '0.8rem', marginBottom: '0.2rem' }}>Confidence</div>
          <div style={{ fontWeight: 800, color: isNone ? 'var(--hf-text-secondary)' : 'var(--hf-text-primary)', fontSize: '1rem', opacity: isNone ? 0.85 : 1 }}>
            {pillar.confidence.toFixed(0)}%
          </div>
        </div>
      </div>

      <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
        <button
          type="button"
          className="hf-btn-link"
          onClick={() => {
            if (!isLoading) setExpanded((v) => !v)
          }}
          disabled={isLoading}
        >
          {expanded ? 'Hide' : 'Show'} details
        </button>
      </div>

      {expanded ? (
        <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--hf-border)' }}>
          {pillarNarrative && (
            <div className="hf-muted" style={{ fontSize: '0.95rem', marginBottom: '0.75rem', lineHeight: 1.5 }}>
              {pillarNarrative}
            </div>
          )}
          {PILLAR_LONG_DESCRIPTIONS[pillar_key] ? (
            <div className="hf-muted" style={{ fontSize: '0.95rem', marginBottom: '1rem', lineHeight: 1.5 }}>
              {PILLAR_LONG_DESCRIPTIONS[pillar_key]}
            </div>
          ) : null}
          <div className="hf-label" style={{ marginBottom: '0.5rem' }}>
            Details
          </div>

          <div className="hf-muted" style={{ fontSize: '0.95rem' }}>
            {pillar_key === 'natural_beauty' && (() => {
              const fromProps = naturalBeautyPreference && naturalBeautyPreference.length > 0 ? naturalBeautyPreference : null
              const fromPillar = Array.isArray((pillar as any)?.summary?.natural_beauty_preference) && (pillar as any).summary.natural_beauty_preference.length > 0
                ? (pillar as any).summary.natural_beauty_preference as string[]
                : null
              const displayPreference = fromProps ?? fromPillar
              const pref = displayPreference ?? []
              const canChange = Boolean(onNaturalBeautyPreferenceChange)
              return (
                <div style={{ marginBottom: canChange ? '0.85rem' : '0.5rem' }}>
                  <span style={{ fontWeight: 600, color: 'var(--hf-text-primary)' }}>Preference:</span>
                  {canChange ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.35rem' }}>
                      {NATURAL_BEAUTY_PREFERENCE_CHIPS.map(({ value, label }) => {
                        const isAny = value === null
                        const hasAny = !pref.length || (pref.length === 1 && pref[0] === 'no_preference')
                        const chipSelected = isAny ? hasAny : pref.includes(value as string)
                        const atMax = !isAny && pref.length >= 2 && !pref.includes(value as string)
                        const handleClick = () => {
                          if (isAny) {
                            onNaturalBeautyPreferenceChange!(null)
                            return
                          }
                          const current = pref.filter((v) => v !== 'no_preference')
                          if (current.includes(value as string)) {
                            const next = current.filter((v) => v !== value)
                            onNaturalBeautyPreferenceChange!(next.length ? next : null)
                          } else if (current.length >= 2) {
                            onNaturalBeautyPreferenceChange!([current[1], value as string])
                          } else {
                            onNaturalBeautyPreferenceChange!([...current, value as string])
                          }
                        }
                        return (
                          <button
                            key={label}
                            type="button"
                            onClick={(e) => { e.stopPropagation(); handleClick() }}
                            disabled={atMax || rescoring}
                            style={{
                              padding: '0.35rem 0.65rem',
                              borderRadius: 8,
                              fontSize: '0.85rem',
                              fontWeight: chipSelected ? 600 : 400,
                              background: chipSelected ? 'var(--hf-primary-1)' : 'var(--hf-bg-subtle)',
                              color: chipSelected ? 'white' : atMax ? 'var(--hf-text-tertiary)' : 'var(--hf-text-secondary)',
                              border: `1px solid ${chipSelected ? 'var(--hf-primary-1)' : 'var(--hf-border)'}`,
                              cursor: atMax || rescoring ? 'not-allowed' : 'pointer',
                              opacity: atMax || rescoring ? 0.7 : 1,
                            }}
                          >
                            {label}
                          </button>
                        )
                      })}
                      <span className="hf-muted" style={{ fontSize: '0.75rem' }}>(up to 2)</span>
                    </div>
                  ) : (
                    displayPreference ? <>{' '}{displayPreference.join(', ')}</> : null
                  )}
                </div>
              )
            })()}
            {pillar_key === 'neighborhood_amenities' && onIncludeChainsChange ? (
              <div style={{ marginBottom: '0.85rem' }}>
                <label
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    cursor: 'pointer',
                    fontSize: '0.95rem',
                    color: 'var(--hf-text-primary)',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={Boolean(includeChainsValue)}
                    onChange={(e) => onIncludeChainsChange(e.target.checked)}
                    disabled={rescoring}
                  />
                  <span>Include chain businesses</span>
                </label>
              </div>
            ) : null}

            {(() => {
              const spec = PILLAR_DETAILS_SPEC[pillar_key]
              const pillarObj = pillar as unknown as Record<string, unknown>
              const staticTexts: { local_vs_chains?: string } = {}
              if (pillar_key === 'neighborhood_amenities') {
                staticTexts.local_vs_chains = includeChainsValue
                  ? 'Score includes both chains and local places.'
                  : 'Score focuses on independent/local businesses.'
              }

              if (spec) {
                const metricRows = spec.metrics
                  .map((metric) => {
                    const value = formatSpecMetricValue(pillarObj, metric, staticTexts)
                    if (value === null) return null
                      return { label: metric.label, value }
                  })
                  .filter((row): row is { label: string; value: string } => row !== null)

                return (
                  <>
                    <p style={{ margin: 0, marginBottom: '0.75rem', color: 'var(--hf-text-primary)', lineHeight: 1.45 }}>
                      {spec.topLine}
                    </p>
                    {Boolean(pillar.data_quality?.degraded) && (
                      <div
                        role="status"
                        style={{
                          marginBottom: '0.75rem',
                          padding: '0.5rem 0.65rem',
                          borderRadius: 8,
                          background: 'rgba(200, 184, 74, 0.12)',
                          border: '1px solid rgba(168, 154, 58, 0.35)',
                          fontSize: '0.9rem',
                          color: 'var(--hf-text-primary)',
                        }}
                      >
                        {spec.degradedMessage}
                      </div>
                    )}
                    {metricRows.length > 0 ? (
                      <div style={{ display: 'grid', gap: '0.5rem' }}>
                        {metricRows.map(({ label, value }) => {
                          const explainer = METRIC_EXPLAINERS[`${pillar_key}:${label}`]
                          return (
                            <div
                              key={label}
                              style={{
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '0.15rem',
                              }}
                            >
                              <div
                                style={{
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'baseline',
                                  gap: '0.5rem',
                                }}
                              >
                                <span style={{ textTransform: 'none' }}>{label}</span>
                                <span
                                  style={{
                                    fontWeight: 700,
                                    color: 'var(--hf-text-primary)',
                                    textAlign: 'right',
                                    whiteSpace: 'nowrap',
                                  }}
                                >
                                  {value}
                                </span>
                              </div>
                              {explainer && (
                                <span
                                  style={{
                                    fontSize: '0.8rem',
                                    color: 'var(--hf-text-secondary)',
                                    lineHeight: 1.3,
                                  }}
                                >
                                  {explainer}
                                </span>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    ) : (
                      <div>No additional details available.</div>
                    )}
                  </>
                )
              }

              // Fallback: generic summary/breakdown when no spec or missing data
              if (summary && Object.keys(summary).length > 0) {
                return (
                  <div style={{ display: 'grid', gap: '0.75rem' }}>
                    {Object.entries(summary).map(([key, value]) => {
                      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
                        return (
                          <div key={key}>
                            <div style={{ fontWeight: 800, color: 'var(--hf-text-primary)', textTransform: 'capitalize', marginBottom: '0.25rem' }}>
                              {key.replace(/_/g, ' ')}
                            </div>
                            <div style={{ display: 'grid', gap: '0.35rem', paddingLeft: '0.75rem' }}>
                              {Object.entries(value).map(([subKey, subValue]) => (
                                <div key={subKey} style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                                  <span style={{ textTransform: 'capitalize' }}>{subKey.replace(/_/g, ' ')}</span>
                                  <span style={{ fontWeight: 700, color: 'var(--hf-text-primary)' }}>
                                    {formatValue(subValue, 1)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )
                      }
                      if (Array.isArray(value)) {
                        return (
                          <div key={key} style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                            <span style={{ textTransform: 'capitalize' }}>{key.replace(/_/g, ' ')}</span>
                            <span style={{ fontWeight: 700, color: 'var(--hf-text-primary)', textAlign: 'right' }}>
                              {value.length ? value.map((v) => String(v)).join(', ') : '—'}
                            </span>
                          </div>
                        )
                      }
                      return (
                        <div key={key} style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem' }}>
                          <span style={{ textTransform: 'capitalize' }}>{key.replace(/_/g, ' ')}</span>
                          <span style={{ fontWeight: 700, color: 'var(--hf-text-primary)' }}>
                            {formatValue(value)}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                )
              }
              return <div>No additional details available.</div>
            })()}
          </div>

          {onRescorePillar ? (
            <div style={{ marginTop: '1.25rem' }}>
              {pillar.confidence < 50 && (
                <div
                  role="status"
                  style={{
                    fontSize: '0.9rem',
                    padding: '0.6rem 0.75rem',
                    marginBottom: '0.75rem',
                    borderRadius: 8,
                    background: 'rgba(200, 184, 74, 0.15)',
                    border: '1px solid rgba(168, 154, 58, 0.4)',
                    color: 'var(--hf-text-primary)',
                  }}
                >
                  Low confidence data — rescore for better results
                </div>
              )}
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault()
                  onRescorePillar(pillar_key)
                }}
                disabled={rescoring}
                className="hf-btn-link"
                style={{
                  fontSize: pillar.confidence >= 50 ? '0.85rem' : '0.95rem',
                  padding: pillar.confidence >= 50 ? '0.25rem 0' : '0.5rem 0',
                  opacity: rescoring ? 0.7 : 1,
                  ...(pillar.confidence >= 50 ? { color: 'var(--hf-text-secondary)' } : {}),
                }}
              >
                {rescoring ? 'Rescoring…' : 'Rescore this pillar'}
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
