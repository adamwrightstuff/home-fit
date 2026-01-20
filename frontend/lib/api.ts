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
  while (response.status === 202 || response.status === 409) {
    const payload = await response.json().catch(() => null);
    const jobId = payload?.job_id;
    if (!jobId) {
      throw new Error('Scoring is queued, but no job_id was returned');
    }
    if (Date.now() - start > maxWaitMs) {
      throw new Error('Scoring is taking longer than expected. Please try again.');
    }
    await new Promise((r) => setTimeout(r, pollDelayMs));
    pollDelayMs = Math.min(2500, Math.round(pollDelayMs * 1.25));
    response = await fetchOnce(`${API_BASE_URL}/api/score?job_id=${encodeURIComponent(jobId)}`);
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error?.detail || `API error: ${response.status}`);
  }

  const json = await response.json();
  if (!json || typeof json.total_score !== 'number') {
    throw new Error('Unexpected scoring response. Please refresh and try again.');
  }
  return json;
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
