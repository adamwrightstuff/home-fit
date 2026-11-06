import { buildWhoLivesHere } from '@/lib/whoLivesHere'

/**
 * Plain facts about the residents. A description, not a score: no weight, not counted in the total.
 * Race and income distributions are deliberately not shown (docs/PILLAR_DIVERSITY.md, owner ruling 2026-10-28).
 */
export default function WhoLivesHere({ pillars }: { pillars: unknown }) {
  const { groups } = buildWhoLivesHere(pillars)
  if (groups.length === 0) return null
  return (
    <section className="mb-8" aria-label="Who lives here">
      <h2 className="mb-1 text-lg font-bold text-[var(--hf-text-primary)]">Who lives here</h2>
      <p className="mb-3 text-xs leading-relaxed text-[var(--hf-text-tertiary)]">
        Residents (Census ACS 2022). Each figure covers the neighborhood tract or the whole city or town that the Census data for this place describes. Facts, not a score, and not counted in the total.
        Incomes are capped by the Census at $250,000 and home values at $2,000,000.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {groups.map((g) => (
          <div key={g.title} className="rounded-2xl border border-[var(--hf-border)] bg-[var(--hf-card-bg)] p-4">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--hf-text-tertiary)]">{g.title}</div>
            <dl className="space-y-1">
              {g.rows.map((r) => (
                <div key={r.label} className="flex items-baseline justify-between gap-3">
                  <dt className="text-sm text-[var(--hf-text-secondary)]">{r.label}</dt>
                  <dd className="text-sm font-bold text-[var(--hf-text-primary)]">{r.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </section>
  )
}
