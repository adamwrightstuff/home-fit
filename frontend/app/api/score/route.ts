import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';

export const runtime = 'nodejs';

const RAILWAY_API_BASE_URL =
  process.env.RAILWAY_API_BASE_URL || 'https://home-fit-production.up.railway.app';
const HOMEFIT_PROXY_SECRET = process.env.HOMEFIT_PROXY_SECRET || '';
const PREMIUM_CODES = new Set(
  (process.env.HOMEFIT_SCHOOLS_PREMIUM_CODES || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
);

function md5(input: string): string {
  return crypto.createHash('md5').update(input).digest('hex');
}

function getClientIp(req: NextRequest): string {
  const xff = req.headers.get('x-forwarded-for');
  if (xff) return xff.split(',')[0]?.trim() || 'unknown';
  return req.ip || 'unknown';
}

export async function GET(req: NextRequest) {
  if (process.env.HOMEFIT_DISABLE_SCORE === '1') {
    return NextResponse.json({ detail: 'Temporarily disabled' }, { status: 503 });
  }

  if (!HOMEFIT_PROXY_SECRET) {
    return NextResponse.json(
      { detail: 'Server misconfigured: missing HOMEFIT_PROXY_SECRET' },
      { status: 500 }
    );
  }

  const sp = req.nextUrl.searchParams;
  const location = sp.get('location')?.trim();
  if (!location) {
    return NextResponse.json({ detail: 'Missing required query param: location' }, { status: 400 });
  }

  // Forward only a small, explicit allowlist of query params.
  const upstreamParams = new URLSearchParams();
  upstreamParams.set('location', location);

  for (const key of ['tokens', 'priorities', 'include_chains', 'diagnostics', 'only'] as const) {
    const v = sp.get(key);
    if (v !== null && v !== undefined) upstreamParams.set(key, v);
  }

  // Schools gating: require a premium code to reach the backend with enable_schools=true.
  const enableSchools = sp.get('enable_schools');
  const premiumCode = sp.get('premium_code')?.trim() || '';
  const premiumOk = Boolean(premiumCode) && PREMIUM_CODES.has(premiumCode);

  if (enableSchools !== null) {
    // Default to "false" unless premium passes.
    upstreamParams.set('enable_schools', premiumOk ? enableSchools : 'false');
  }

  const url = `${RAILWAY_API_BASE_URL}/score?${upstreamParams.toString()}`;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 25_000);
  const start = Date.now();

  try {
    const upstream = await fetch(url, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        'X-HomeFit-Proxy-Secret': HOMEFIT_PROXY_SECRET,
        ...(premiumOk ? { 'X-HomeFit-Premium-Code': premiumCode } : {}),
      },
      signal: controller.signal,
      cache: 'no-store',
    });

    const durationMs = Date.now() - start;
    const locationHash = md5(location.toLowerCase()).slice(0, 10);
    const ip = getClientIp(req);
    // Minimal operational logging (avoid logging addresses)
    console.log(
      JSON.stringify({
        msg: 'proxy_score',
        status: upstream.status,
        duration_ms: durationMs,
        ip,
        location_hash: locationHash,
      })
    );

    const bodyText = await upstream.text();
    const contentType = upstream.headers.get('content-type') || 'application/json';

    return new NextResponse(bodyText, {
      status: upstream.status,
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'no-store',
      },
    });
  } catch (err) {
    const durationMs = Date.now() - start;
    const locationHash = md5(location.toLowerCase()).slice(0, 10);
    const ip = getClientIp(req);
    console.log(
      JSON.stringify({
        msg: 'proxy_score_error',
        duration_ms: durationMs,
        ip,
        location_hash: locationHash,
        error: err instanceof Error ? err.message : String(err),
      })
    );

    return NextResponse.json(
      { detail: 'Upstream request failed or timed out' },
      { status: 502, headers: { 'Cache-Control': 'no-store' } }
    );
  } finally {
    clearTimeout(timeout);
  }
}

