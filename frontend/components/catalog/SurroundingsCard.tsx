import { NEIGHBOR_CATEGORIES, SURROUNDINGS_EXPLAINER, surroundingsGroups, type Surroundings } from '@/lib/surroundings'

/** Income, home value and safety nearby vs here, grouped by neighbor category. A description, not a score (docs/SURROUNDINGS.md). */
export default function SurroundingsCard({ surroundings, size = 'compact' }: { surroundings?: Surroundings | null; size?: 'compact' | 'page' }) {
  const groups = surroundingsGroups(surroundings)
  if (groups.length === 0) return null
  const page = size === 'page'
  const text = page ? 'text-sm' : 'text-[0.75rem]'
  const neighbors = surroundings?.neighbors?.filter(Boolean) ?? []
  return (
    <div className={`rounded-xl border border-[var(--hf-border)] bg-[var(--hf-bg-subtle)] ${page ? 'p-4' : 'px-3 py-2.5'}`} aria-label="Around here">
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="text-[0.65rem] font-semibold uppercase tracking-wide text-[var(--hf-text-tertiary)]" title={SURROUNDINGS_EXPLAINER}>
          Around here
        </span>
        <span className="grid grid-cols-2 gap-3 text-right text-[0.65rem] uppercase tracking-wide text-[var(--hf-text-tertiary)]" style={{ minWidth: page ? 140 : 104 }}>
          <span>Nearby</span>
          <span>Here</span>
        </span>
      </div>
      <div className="space-y-1.5">
        {groups.map((g) => (
          <div key={g.key}>
            <div className="text-[0.6rem] font-semibold uppercase tracking-wide text-[var(--hf-text-tertiary)]">{g.label}</div>
            <dl className="space-y-0.5">
              {g.rows.map((r) => (
                <div key={r.label} className="flex items-baseline justify-between gap-2">
                  <dt className={`${text} text-[var(--hf-text-secondary)]`}>{r.label}</dt>
                  <dd className={`grid grid-cols-2 gap-3 text-right tabular-nums ${text}`} style={{ minWidth: page ? 140 : 104 }}>
                    <span className="text-[var(--hf-text-secondary)]">{r.around}</span>
                    <span className="font-bold text-[var(--hf-text-primary)]">{r.here}</span>
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
        {page &&
          NEIGHBOR_CATEGORIES.filter((c) => c.notShown).map((c) => (
            <div key={c.key}>
              <div className="text-[0.6rem] font-semibold uppercase tracking-wide text-[var(--hf-text-tertiary)]">{c.label}</div>
              <p className="m-0 text-xs leading-snug text-[var(--hf-text-tertiary)]">{c.notShown}</p>
            </div>
          ))}
      </div>
      {neighbors.length > 0 && (
        <p className={`mt-1.5 ${page ? 'text-xs' : 'text-[0.68rem]'} leading-snug text-[var(--hf-text-tertiary)]`}>
          Closest: {neighbors.join(', ')}
          {page && <><br />{SURROUNDINGS_EXPLAINER}</>}
        </p>
      )}
    </div>
  )
}
