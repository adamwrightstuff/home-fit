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
  
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
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
