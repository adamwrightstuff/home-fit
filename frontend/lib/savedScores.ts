/** Client helpers for saved-scores API (cookies sent automatically). */

export interface SavedScoreRow {
  id: string
  input: string
  coordinates: { lat: number; lon: number }
  location_info: { city: string; state: string; zip: string }
  score_payload: unknown
  priorities: unknown
  created_at: string
  updated_at: string
}

export async function listSavedScores(): Promise<SavedScoreRow[]> {
  const res = await fetch('/api/me/saved-scores', { credentials: 'include' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getSavedScore(id: string): Promise<SavedScoreRow> {
  const res = await fetch(`/api/me/saved-scores/${id}`, { credentials: 'include' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function saveScore(scorePayload: unknown, priorities: unknown): Promise<{ id: string }> {
  const res = await fetch('/api/me/saved-scores', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ scorePayload, priorities }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || res.statusText)
  return data
}

export async function updateSavedScore(
  id: string,
  updates: { scorePayload?: unknown; priorities?: unknown }
): Promise<{ id: string }> {
  const res = await fetch(`/api/me/saved-scores/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(updates),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || res.statusText)
  return data
}

export async function deleteSavedScore(id: string): Promise<void> {
  const res = await fetch(`/api/me/saved-scores/${id}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await res.text())
}
