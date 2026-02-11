import { ScoreResponse, ScoreRequestParams } from '@/types/api';

// For production, the browser should call same-origin Vercel API routes (which proxy to Railway).
const API_BASE_URL = '';

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
  let payload: Record<string, unknown> | null = null;
  // Some environments return 409 {job_id} while queued/running.
  // In rare dev-bundler edge cases we can also get 200 {job_id} with no total_score.
  // Treat any {job_id} response as a pollable job until we get a real ScoreResponse.
  while (response.status === 202 || response.status === 409 || response.status === 200) {
    payload = await response.json().catch(() => null);

    // Success case
    if (payload && typeof payload.total_score === 'number') {
      return payload as ScoreResponse;
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
      response = await fetchOnce(`${API_BASE_URL}/api/score?job_id=${encodeURIComponent(jobId)}`);
      continue;
    }

    // If we got here with a 200 but not a score (and no pollable job), break and error below.
    break;
  }

  if (!response.ok) {
    // Use payload if we already read the body in the loop; otherwise read once.
    const errorPayload = payload ?? await response.json().catch(() => ({ detail: 'Unknown error' }));
    const detail = errorPayload && typeof errorPayload === 'object' && 'detail' in errorPayload
      ? (errorPayload as { detail?: string }).detail
      : 'Unknown error';
    throw new Error(detail || `API error: ${response.status}`);
  }

  // Reuse payload from loop—response body was already consumed above, avoid double-read.
  const json = payload;
  if (!json || typeof json.total_score !== 'number') {
    throw new Error('Unexpected scoring response. Please refresh and try again.');
  }
  return json as ScoreResponse;
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
  // Launch-week hardening: SSE is disabled. Keep the function shape so
  // older UI code won't crash, but fail fast.
  const error = new Error('Streaming is disabled (launch hardening)');
  if (onError) onError(error);
  onEvent({ status: 'error', message: error.message });
  return () => {};
}
