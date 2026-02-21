import { NextRequest } from 'next/server';

export const runtime = 'nodejs';
// 120s so Economic Opportunity Focus (job_categories) has time to complete extra Census calls
export const maxDuration = 120;

const RAILWAY_API_BASE_URL =
  process.env.RAILWAY_API_BASE_URL || 'https://home-fit-production.up.railway.app';
const HOMEFIT_PROXY_SECRET = process.env.HOMEFIT_PROXY_SECRET || '';
const STREAM_TIMEOUT_MS = Number(process.env.HOMEFIT_SCORE_PROXY_TIMEOUT_MS || '90000');
/** Extra time when Economic Opportunity Focus (job_categories) is used — pillar does 2 more Census API calls. */
const STREAM_TIMEOUT_MS_WITH_JOB_CATEGORIES = Number(
  process.env.HOMEFIT_SCORE_PROXY_TIMEOUT_MS_JOB_CATEGORIES || '150000'
);
const PREMIUM_CODES = new Set(
  (process.env.HOMEFIT_SCHOOLS_PREMIUM_CODES || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
);

export async function GET(req: NextRequest) {
  if (process.env.HOMEFIT_DISABLE_SCORE === '1') {
    return new Response(JSON.stringify({ detail: 'Temporarily disabled' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const sp = req.nextUrl.searchParams;
  const location = sp.get('location')?.trim();
  if (!location) {
    return new Response(JSON.stringify({ detail: 'Missing required query param: location' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const params = new URLSearchParams();
  params.set('location', location);
  for (const key of ['tokens', 'priorities', 'include_chains', 'job_categories', 'only'] as const) {
    const v = sp.get(key);
    if (v != null) params.set(key, v);
  }
  const enableSchools = sp.get('enable_schools');
  const premiumCode = sp.get('premium_code')?.trim() || '';
  const premiumOk = Boolean(premiumCode) && PREMIUM_CODES.has(premiumCode);
  if (enableSchools != null) {
    params.set('enable_schools', premiumOk ? enableSchools : 'false');
  }

  const url = `${RAILWAY_API_BASE_URL}/score/stream?${params.toString()}`;
  const hasJobCategories = sp.get('job_categories')?.trim().length > 0;
  const streamTimeoutMs = hasJobCategories ? STREAM_TIMEOUT_MS_WITH_JOB_CATEGORIES : STREAM_TIMEOUT_MS;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), streamTimeoutMs);

  try {
    const upstream = await fetch(url, {
      method: 'GET',
      headers: {
        Accept: 'text/event-stream',
        ...(HOMEFIT_PROXY_SECRET ? { 'X-HomeFit-Proxy-Secret': HOMEFIT_PROXY_SECRET } : {}),
        ...(premiumOk ? { 'X-HomeFit-Premium-Code': premiumCode } : {}),
      },
      signal: controller.signal,
      cache: 'no-store',
    });

    clearTimeout(timeout);

    if (!upstream.ok) {
      const text = await upstream.text();
      let body: { detail?: string } = { detail: 'Stream request failed' };
      try {
        body = JSON.parse(text);
      } catch {
        body = { detail: text || upstream.statusText };
      }
      return new Response(JSON.stringify(body), {
        status: upstream.status,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const headers = new Headers();
    headers.set('Content-Type', upstream.headers.get('content-type') || 'text/event-stream');
    headers.set('Cache-Control', 'no-cache');
    headers.set('Connection', 'keep-alive');
    headers.set('X-Accel-Buffering', 'no');

    return new Response(upstream.body, {
      status: 200,
      headers,
    });
  } catch (err) {
    clearTimeout(timeout);
    const msg = err instanceof Error ? err.message : String(err);
    return new Response(
      JSON.stringify({
        detail: 'Stream request failed or timed out',
        error: msg,
      }),
      {
        status: 502,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}
