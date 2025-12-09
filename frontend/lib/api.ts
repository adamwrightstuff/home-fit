import { ScoreResponse, ScoreRequestParams } from '@/types/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://home-fit-production.up.railway.app';

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

  const url = `${API_BASE_URL}/score?${searchParams.toString()}`;
  
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
  const response = await fetch(`${API_BASE_URL}/health`, {
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
