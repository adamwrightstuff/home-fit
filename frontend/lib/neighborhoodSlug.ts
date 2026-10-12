/**
 * Canonical URL slugs for catalog neighborhoods.
 * Scheme: {name}-{county_borough}-{state_abbr}, all slugified, e.g.
 * "park-slope-brooklyn-ny". Unique across all 416 catalog places
 * (verified: the single same-name collision, Ridgewood NJ vs Ridgewood
 * Queens, is disambiguated by county_borough).
 *
 * Shared between server (generateStaticParams, sitemap) and client
 * (catalog row links) so slugs agree everywhere.
 */

export function slugify(s: string | null | undefined): string {
  const out = String(s ?? '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return out || 'x'
}

export interface SlugCatalog {
  name?: string | null
  county_borough?: string | null
  state_abbr?: string | null
}

export function placeSlug(c: SlugCatalog): string {
  return `${slugify(c.name)}-${slugify(c.county_borough)}-${slugify(c.state_abbr)}`
}
