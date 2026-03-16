import { ScoreResponse, ScoreRequestParams, GeocodeResult } from '@/types/api';

// For production, the browser should call same-origin Vercel API routes (which proxy to Railway).
const API_BASE_URL = '';

/** OpenStreetMap Nominatim fallback when our backend is down. Returns GeocodeResult shape. */
async function geocodeWithNominatim(location: string): Promise<GeocodeResult | null> {
  try {
    const q = location.trim();
    if (!q) return null;
    const res = await fetch(
      `https://nominatim.openstreetmap.org/search?${new URLSearchParams({
        q,
        format: 'json',
        limit: '1',
      })}`,
      { headers: { Accept: 'application/json', 'User-Agent': 'HomeFit/1.0 (location search fallback)' } }
    );
    if (!res.ok) return null;
    const arr = (await res.json()) as Array<{ lat: string; lon: string; display_name?: string; address?: Record<string, string> }>;
    const first = arr?.[0];
    if (!first || first.lat == null || first.lon == null) return null;
    const lat = parseFloat(first.lat);
    const lon = parseFloat(first.lon);
    if (Number.isNaN(lat) || Number.isNaN(lon)) return null;
    const addr = first.address || {};
    const city = addr.city || addr.town || addr.village || addr.municipality || '';
    const state = addr.state || '';
    const zip_code = addr.postcode || '';
    const display_name = first.display_name || [city, state, zip_code].filter(Boolean).join(', ') || location;
    return { lat, lon, city, state, zip_code, display_name };
  } catch {
    return null;
  }
}

/** Geocode a place to show map and "you are about to search here". No pillar work. Uses backend; if backend is down (502/503) or unreachable, falls back to OpenStreetMap Nominatim so location search still works. */
export async function getGeocode(location: string): Promise<GeocodeResult> {
  const url = `${API_BASE_URL}/api/geocode?location=${encodeURIComponent(location.trim())}`;
  const fetchOpts: RequestInit = { method: 'GET', headers: { Accept: 'application/json' } };

  const maxAttempts = 3;
  const retryDelaysMs = [2000, 4000];

  let lastError: Error | null = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      let res = await fetch(url, fetchOpts);
      if (res.status === 502 || res.status === 503) {
        for (const delayMs of [5000, 10000, 15000]) {
          await new Promise((r) => setTimeout(r, delayMs));
          res = await fetch(url, fetchOpts);
          if (res.status !== 502 && res.status !== 503) break;
        }
      }

      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = typeof data?.detail === 'string' ? data.detail : 'Could not find that location.';
        const message =
          res.status === 502 || res.status === 503
            ? (detail.toLowerCase().includes('try again') ? detail : 'Location service is starting up. Please try again in a moment.')
            : detail;
        lastError = new Error(message);
        if (attempt < maxAttempts) {
          await new Promise((r) => setTimeout(r, retryDelaysMs[attempt - 1]));
          continue;
        }
        break;
      }
      if (typeof data?.lat !== 'number' || typeof data?.lon !== 'number') {
        lastError = new Error('Invalid geocode response.');
        if (attempt < maxAttempts) {
          await new Promise((r) => setTimeout(r, retryDelaysMs[attempt - 1]));
          continue;
        }
        break;
      }
      return data as GeocodeResult;
    } catch (e) {
      lastError = e instanceof Error ? e : new Error(String(e));
      if (attempt < maxAttempts) {
        await new Promise((r) => setTimeout(r, retryDelaysMs[attempt - 1]));
        continue;
      }
      break;
    }
  }

  // Backend down or unreachable: try OpenStreetMap so user can at least search and see the map
  const fallback = await geocodeWithNominatim(location.trim());
  if (fallback) return fallback;

  throw lastError ?? new Error('Could not find that location.');
}

export async function getScore(params: ScoreRequestParams): Promise<ScoreResponse> {
  const searchParams = new URLSearchParams({
    location: params.location,
  });

  if (params.tokens) {
    searchParams.append('tokens', params.tokens);
  }
  if (params.priorities) {
    searchParams.append('priorities', params.priorities);
  }
  if (params.job_categories) {
    searchParams.append('job_categories', params.job_categories);
  }
  if (params.include_chains !== undefined) {
    searchParams.append('include_chains', params.include_chains.toString());
  }
  if (params.enable_schools !== undefined) {
    searchParams.append('enable_schools', params.enable_schools.toString());
  }
  if (params.only) {
    searchParams.append('only', params.only);
  }
  if (params.natural_beauty_preference) {
    searchParams.append('natural_beauty_preference', params.natural_beauty_preference);
  }
  if (params.built_character_preference) {
    searchParams.append('built_character_preference', params.built_character_preference);
  }
  if (params.built_density_preference) {
    searchParams.append('built_density_preference', params.built_density_preference);
  }

  // Premium schools gating: include saved premium code (if any).
  // This is validated server-side; sending it does not guarantee access.
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      const premiumCode = window.sessionStorage.getItem('homefit_premium_code');
      if (premiumCode) {
        searchParams.append('premium_code', premiumCode);
      }
    }
  } catch {
    // ignore storage errors
  }

  const url = `${API_BASE_URL}/api/score?${searchParams.toString()}`;
  
  // Launch hardening: scoring can take longer than a serverless request limit.
  // We transparently handle async job polling when the API returns 202 {job_id}.
  const start = Date.now();
  const maxWaitMs = 8 * 60 * 1000; // 8 min — slow pillars (Natural Beauty, Census retries) can take 1–2 min
  let pollDelayMs = 750;

  async function fetchOnce(fetchUrl: string): Promise<Response> {
    return fetch(fetchUrl, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  let response = await fetchOnce(url);
  // Retry on 502 for initial request (cold start). Backend can take ~20s to join LB pool after container start.
  if (response.status === 502 && !searchParams.has('job_id')) {
    for (const delayMs of [15000, 20000, 25000]) {
      await new Promise((r) => setTimeout(r, delayMs));
      response = await fetchOnce(url);
      if (response.status !== 502) break;
    }
  }
  let payload: Record<string, unknown> | null = null;
  // Some environments return 409 {job_id} while queued/running.
  // In rare dev-bundler edge cases we can also get 200 {job_id} with no total_score.
  // Treat any {job_id} response as a pollable job until we get a real ScoreResponse.
  while (response.status === 202 || response.status === 409 || response.status === 200) {
    payload = await response.json().catch(() => null);

    // Success case: proxy may return either the result object or the full job wrapper
    if (payload && typeof (payload as { total_score?: number }).total_score === 'number') {
      return payload as unknown as ScoreResponse;
    }
    if (payload && (payload as { result?: unknown }).result && typeof ((payload as { result: { total_score?: number } }).result?.total_score) === 'number') {
      return (payload as { result: ScoreResponse }).result;
    }

    const jobId = payload?.job_id;
    const status = payload?.status;

    // If we got a job payload, keep polling.
    if (jobId && (response.status === 202 || response.status === 409 || status === 'queued' || status === 'running')) {
      if (Date.now() - start > maxWaitMs) {
        throw new Error('Scoring is taking longer than expected. Please try again.');
      }
      await new Promise((r) => setTimeout(r, pollDelayMs));
      pollDelayMs = Math.min(2500, Math.round(pollDelayMs * 1.25));
      response = await fetchOnce(`${API_BASE_URL}/api/score?job_id=${encodeURIComponent(String(jobId))}`);
      // Retry once on 404 (e.g. poll hit a different replica before Redis sync)
      if (response.status === 404) {
        await new Promise((r) => setTimeout(r, 1500));
        response = await fetchOnce(`${API_BASE_URL}/api/score?job_id=${encodeURIComponent(String(jobId))}`);
      }
      continue;
    }

    // Job failed on backend (status: 'error')—surface the actual error
    if (payload && payload.status === 'error') {
      const detail = (payload as { detail?: string }).detail ?? 'Scoring job failed';
      throw new Error(detail);
    }

    // If we got here with a 200 but not a score (and no pollable job), break and error below.
    break;
  }

  if (!response.ok) {
    const errorPayload = payload ?? await response.json().catch(() => null);
    const detail = errorPayload && typeof errorPayload === 'object' && 'detail' in errorPayload
      ? (errorPayload as { detail?: string }).detail
      : null;
    const sub = errorPayload && typeof errorPayload === 'object' && 'error' in errorPayload
      ? (errorPayload as { error?: string }).error
      : null;
    let message =
      (typeof detail === 'string' && detail.trim()) ||
      (typeof sub === 'string' && sub.trim() ? `Upstream error: ${sub}` : null) ||
      `Request failed (${response.status})`;
    if (response.status === 502 && !/try again|waking up|timed out|unavailable/i.test(message)) {
      message += ' Try again in a moment—the server may be waking up.';
    }
    throw new Error(message);
  }

  // Reuse payload from loop—response body was already consumed above, avoid double-read.
  const json = payload;
  if (json && typeof (json as { total_score?: number }).total_score === 'number') {
    return json as unknown as ScoreResponse;
  }
  if (json && (json as { result?: unknown }).result && typeof ((json as { result: { total_score?: number } }).result?.total_score) === 'number') {
    return (json as { result: ScoreResponse }).result;
  }
  const detail = json && typeof json === 'object' && 'detail' in json
    ? (json as { detail?: string }).detail
    : null;
  throw new Error(detail || 'Unexpected scoring response. Please refresh and try again.');
}

/** Fetch a single pillar's score for a location (tap-to-score flow). Uses same polling as getScore. */
export async function getScoreSinglePillar(
  params: Omit<ScoreRequestParams, 'only'> & { pillar: string }
): Promise<ScoreResponse> {
  return getScore({ ...params, only: params.pillar });
}

export async function checkHealth(): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/health`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }

  return response.json();
}

/** Partial pillar progress from job polling: pillar key -> { score } */
export type PartialPillars = Record<string, { score: number }>;

/** Optional options for getScoreWithProgress */
export interface GetScoreWithProgressOptions {
  /** When true, the function will throw a cancelled error and stop polling */
  getCancelled?: () => boolean;
}

/**
 * Job-based scoring with progress. Creates a job then polls until done.
 * Avoids Vercel 60s limit; each request is short. onProgress(partial) is called on each poll when partial is present.
 */
export async function getScoreWithProgress(
  params: ScoreRequestParams,
  onProgress: (partial: PartialPillars) => void,
  options?: GetScoreWithProgressOptions
): Promise<ScoreResponse> {
  const getCancelled = options?.getCancelled ?? (() => false);
  const searchParams = new URLSearchParams({ location: params.location });
  if (params.tokens) searchParams.append('tokens', params.tokens);
  if (params.priorities) searchParams.append('priorities', params.priorities);
  if (params.only) searchParams.append('only', params.only);
  if (params.natural_beauty_preference) searchParams.append('natural_beauty_preference', params.natural_beauty_preference);
  if (params.built_character_preference) searchParams.append('built_character_preference', params.built_character_preference);
  if (params.built_density_preference) searchParams.append('built_density_preference', params.built_density_preference);
  if (params.job_categories) searchParams.append('job_categories', params.job_categories);
  if (params.include_chains !== undefined) searchParams.append('include_chains', params.include_chains.toString());
  if (params.enable_schools !== undefined) searchParams.append('enable_schools', params.enable_schools.toString());
  if (params.lat != null && params.lon != null && Number.isFinite(params.lat) && Number.isFinite(params.lon)) {
    searchParams.append('lat', String(params.lat));
    searchParams.append('lon', String(params.lon));
  }
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      const premiumCode = window.sessionStorage.getItem('homefit_premium_code');
      if (premiumCode) searchParams.append('premium_code', premiumCode);
    }
  } catch {
    /* ignore */
  }

  const url = `${API_BASE_URL}/api/score?${searchParams.toString()}`;
  const maxWaitMs = 8 * 60 * 1000; // 8 min — Natural Beauty / Economic Security can take 1–2 min with retries
  let pollDelayMs = 800;

  let res = await fetch(url, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
  // Retry on 502 (cold start). Backend can take 60s+ to join LB pool after container start.
  if (res.status === 502) {
    for (const delayMs of [20000, 35000, 50000, 65000]) {
      if (getCancelled()) throw new Error('Cancelled');
      await new Promise((r) => setTimeout(r, delayMs));
      res = await fetch(url, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      if (res.status !== 502) break;
    }
  }
  if (getCancelled()) throw new Error('Cancelled');
  const payload = (await res.json().catch(() => null)) as Record<string, unknown> | null;
  const jobId = payload?.job_id as string | undefined;
  if (!jobId || (res.status !== 202 && res.status !== 409 && res.status !== 200)) {
    if (payload && typeof (payload as { total_score?: number }).total_score === 'number') {
      return payload as unknown as ScoreResponse;
    }
    if (payload && (payload as { status?: string }).status === 'error') {
      const detail = (payload as { detail?: string }).detail ?? 'Scoring job failed';
      throw new Error(detail);
    }
    let detail = payload && typeof payload === 'object' && 'detail' in payload
      ? (payload as { detail?: string }).detail
      : res.statusText || 'Failed to start scoring job';
    const errSub = payload && typeof payload === 'object' && 'error' in payload
      ? (payload as { error?: string }).error
      : null;
    if (res.status === 502) {
      if (typeof errSub === 'string' && errSub.trim() && !detail.includes(errSub)) {
        detail = detail && detail.trim() ? `${detail} (${errSub})` : errSub;
      }
      if (!/try again|waking up|timed out|unavailable/i.test(detail)) {
        detail = (detail && String(detail).trim() ? `${detail}. ` : '') + 'Try again in a moment—the server may be waking up.';
      }
    }
    throw new Error(detail || `API error: ${res.status}`);
  }

  const start = Date.now();
  const pollUrl = `${API_BASE_URL}/api/score?job_id=${encodeURIComponent(jobId)}`;
  for (;;) {
    await new Promise((r) => setTimeout(r, pollDelayMs));
    if (getCancelled()) throw new Error('Cancelled');
    pollDelayMs = Math.min(2500, Math.round(pollDelayMs * 1.15));
    if (Date.now() - start > maxWaitMs) {
      throw new Error('Scoring is taking longer than expected. Please try again.');
    }

    let pollRes = await fetch(pollUrl, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    // Retry poll on 502 (backend cold start or transient failure)
    if (pollRes.status === 502) {
      for (const delayMs of [2000, 3000, 4000]) {
        if (getCancelled()) throw new Error('Cancelled');
        await new Promise((r) => setTimeout(r, delayMs));
        pollRes = await fetch(pollUrl, {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        });
        if (pollRes.status !== 502) break;
      }
    }
    if (getCancelled()) throw new Error('Cancelled');
    const pollPayload = (await pollRes.json().catch(() => null)) as Record<string, unknown> | null;
    const status = pollPayload?.status as string | undefined;

    if (pollRes.status === 502) {
      const detail =
        (pollPayload && typeof (pollPayload as { detail?: string }).detail === 'string')
          ? (pollPayload as { detail: string }).detail
          : 'Backend temporarily unavailable.';
      throw new Error(detail + ' Try again in a moment.');
    }

    if (pollPayload?.partial && typeof pollPayload.partial === 'object') {
      onProgress(pollPayload.partial as PartialPillars);
    }

    // Proxy returns 200 with body = result only (no wrapper); backend returns { status, result }
    if (pollRes.status === 200 && pollPayload && typeof (pollPayload as { total_score?: number }).total_score === 'number') {
      return pollPayload as unknown as ScoreResponse;
    }
    if (status === 'done' && pollPayload?.result) {
      return pollPayload.result as unknown as ScoreResponse;
    }
    if (status === 'error') {
      const detail = (pollPayload as { detail?: string }).detail ?? 'Scoring job failed';
      throw new Error(detail);
    }
  }
}

export interface StreamEvent {
  status: 'started' | 'analyzing' | 'complete' | 'done' | 'error';
  pillar?: string;
  score?: number;
  completed?: number;
  total?: number;
  message?: string;
  location?: string;
  coordinates?: { lat: number; lon: number };
  response?: ScoreResponse;
  error?: string;
}

export function streamScore(
  params: ScoreRequestParams,
  onEvent: (event: StreamEvent) => void,
  onError?: (error: Error) => void
): () => void {
  const searchParams = new URLSearchParams({ location: params.location });
  if (params.tokens) searchParams.append('tokens', params.tokens);
  if (params.priorities) searchParams.append('priorities', params.priorities);
  if (params.job_categories) searchParams.append('job_categories', params.job_categories);
  if (params.include_chains !== undefined) searchParams.append('include_chains', params.include_chains.toString());
  if (params.enable_schools !== undefined) searchParams.append('enable_schools', params.enable_schools.toString());
  if (params.natural_beauty_preference) searchParams.append('natural_beauty_preference', params.natural_beauty_preference);
  if (params.built_character_preference) searchParams.append('built_character_preference', params.built_character_preference);
  if (params.built_density_preference) searchParams.append('built_density_preference', params.built_density_preference);
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      const premiumCode = window.sessionStorage.getItem('homefit_premium_code');
      if (premiumCode) searchParams.append('premium_code', premiumCode);
    }
  } catch {
    /* ignore */
  }

  const url = `${API_BASE_URL}/api/score/stream?${searchParams.toString()}`;
  const controller = new AbortController();
  let cancelled = false;

  (async () => {
    try {
      const res = await fetch(url, {
        method: 'GET',
        headers: { Accept: 'text/event-stream' },
        signal: controller.signal,
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        const detail = (errBody as { detail?: string })?.detail || res.statusText || `HTTP ${res.status}`;
        throw new Error(detail);
      }
      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response body');
      const decoder = new TextDecoder();
      let buffer = '';
      while (!cancelled) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6)) as StreamEvent;
            onEvent(data);
            if (data.status === 'done' && data.response) return;
            if (data.status === 'error') {
              const errData = data as { message?: string; error?: string }
              throw new Error(errData.message || errData.error || 'Stream error')
            }
          } catch (e) {
            if (e instanceof SyntaxError) continue;
            throw e;
          }
        }
      }
    } catch (e) {
      if (cancelled) return;
      const err = e instanceof Error ? e : new Error(String(e));
      if (onError) onError(err);
      onEvent({ status: 'error', message: err.message });
    }
  })();

  return () => {
    cancelled = true;
    controller.abort();
  };
}
