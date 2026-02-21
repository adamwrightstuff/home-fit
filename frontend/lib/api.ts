import { ScoreResponse, ScoreRequestParams, GeocodeResult } from '@/types/api';

// For production, the browser should call same-origin Vercel API routes (which proxy to Railway).
const API_BASE_URL = '';

/** Geocode a place to show map and "you are about to search here". No pillar work. */
export async function getGeocode(location: string): Promise<GeocodeResult> {
  const res = await fetch(
    `${API_BASE_URL}/api/geocode?location=${encodeURIComponent(location.trim())}`,
    { method: 'GET', headers: { Accept: 'application/json' } }
  );
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : 'Could not find that location.';
    throw new Error(detail);
  }
  if (typeof data?.lat !== 'number' || typeof data?.lon !== 'number') {
    throw new Error('Invalid geocode response.');
  }
  return data as GeocodeResult;
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
  const maxWaitMs = 4 * 60 * 1000; // client-side cap (keep UI responsive)
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
  // Retry on 502 for initial request (cold start); proxy times out at 50s so we're under Vercel 60s limit
  if (response.status === 502 && !searchParams.has('job_id')) {
    for (const delayMs of [5000, 8000, 12000]) {
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
    if (response.status === 502) {
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
  if (params.job_categories) searchParams.append('job_categories', params.job_categories);
  if (params.include_chains !== undefined) searchParams.append('include_chains', params.include_chains.toString());
  if (params.enable_schools !== undefined) searchParams.append('enable_schools', params.enable_schools.toString());
  try {
    if (typeof window !== 'undefined' && window.sessionStorage) {
      const premiumCode = window.sessionStorage.getItem('homefit_premium_code');
      if (premiumCode) searchParams.append('premium_code', premiumCode);
    }
  } catch {
    /* ignore */
  }

  const url = `${API_BASE_URL}/api/score?${searchParams.toString()}`;
  const maxWaitMs = 4 * 60 * 1000;
  let pollDelayMs = 800;

  const res = await fetch(url, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' },
  });
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
    const detail = payload && typeof payload === 'object' && 'detail' in payload
      ? (payload as { detail?: string }).detail
      : res.statusText || 'Failed to start scoring job';
    throw new Error(detail || `API error: ${res.status}`);
  }

  const start = Date.now();
  for (;;) {
    await new Promise((r) => setTimeout(r, pollDelayMs));
    if (getCancelled()) throw new Error('Cancelled');
    pollDelayMs = Math.min(2500, Math.round(pollDelayMs * 1.15));
    if (Date.now() - start > maxWaitMs) {
      throw new Error('Scoring is taking longer than expected. Please try again.');
    }

    const pollRes = await fetch(`${API_BASE_URL}/api/score?job_id=${encodeURIComponent(jobId)}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    if (getCancelled()) throw new Error('Cancelled');
    const pollPayload = (await pollRes.json().catch(() => null)) as Record<string, unknown> | null;
    const status = pollPayload?.status as string | undefined;

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
