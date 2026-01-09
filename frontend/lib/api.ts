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

  const url = `${API_BASE_URL}/score/stream?${searchParams.toString()}`;
  
  console.log('streamScore: Connecting to SSE endpoint:', url);
  const eventSource = new EventSource(url);
  let closed = false;

  eventSource.addEventListener('started', (e: MessageEvent) => {
    console.log('streamScore: Received started event:', e.data);
    if (!closed) {
      try {
        const data = JSON.parse(e.data);
        console.log('streamScore: Parsed started data:', data);
        onEvent({ ...data, status: 'started' });
      } catch (err) {
        console.error('streamScore: Error parsing started event:', err);
      }
    }
  });

  eventSource.addEventListener('analyzing', (e: MessageEvent) => {
    if (!closed) {
      const data = JSON.parse(e.data);
      onEvent({ ...data, status: 'analyzing' });
    }
  });

  eventSource.addEventListener('complete', (e: MessageEvent) => {
    if (!closed) {
      const data = JSON.parse(e.data);
      onEvent({ ...data, status: 'complete' });
    }
  });

  eventSource.addEventListener('done', (e: MessageEvent) => {
    if (!closed) {
      const data = JSON.parse(e.data);
      onEvent({ ...data, status: 'done' });
      eventSource.close();
      closed = true;
    }
  });

  eventSource.addEventListener('error', (e: MessageEvent) => {
    if (!closed) {
      try {
        const data = JSON.parse(e.data);
        onEvent({ ...data, status: 'error' });
        if (onError) {
          onError(new Error(data.message || 'Stream error'));
        }
      } catch (err) {
        // If parsing fails, just trigger error handler
        if (onError) {
          onError(new Error('Stream error'));
        }
      }
      eventSource.close();
      closed = true;
    }
  });

  eventSource.onerror = (error) => {
    console.error('streamScore: EventSource error:', error);
    console.error('streamScore: EventSource readyState:', eventSource.readyState);
    // readyState: 0 = CONNECTING, 1 = OPEN, 2 = CLOSED
    if (eventSource.readyState === EventSource.CLOSED) {
      console.error('streamScore: Connection closed unexpectedly');
    }
    if (!closed) {
      if (onError) {
        onError(new Error('EventSource connection error'));
      }
      eventSource.close();
      closed = true;
    }
  };
  
  // Log when connection opens
  eventSource.onopen = () => {
    console.log('streamScore: EventSource connection opened');
  };

  return () => {
    if (!closed) {
      eventSource.close();
      closed = true;
    }
  };
}
