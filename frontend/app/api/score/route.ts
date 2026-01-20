import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';

export const runtime = 'nodejs';
// Vercel/Serverless safety: scoring can legitimately take ~20–40s.
// Allow enough time for typical requests to finish.
export const maxDuration = 60;

const RAILWAY_API_BASE_URL =
  process.env.RAILWAY_API_BASE_URL || 'https://home-fit-production.up.railway.app';
const HOMEFIT_PROXY_SECRET = process.env.HOMEFIT_PROXY_SECRET || '';
const SCORE_PROXY_TIMEOUT_MS = Number(process.env.HOMEFIT_SCORE_PROXY_TIMEOUT_MS || '55000');
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

  const sp = req.nextUrl.searchParams;
  const jobId = sp.get('job_id')?.trim();
  const location = sp.get('location')?.trim();
  if (!jobId && !location) {
    return NextResponse.json(
      { detail: 'Missing required query param: location (or provide job_id)' },
      { status: 400 }
    );
  }

  // Forward only a small, explicit allowlist of query params.
  const upstreamParams = new URLSearchParams();
  if (location) upstreamParams.set('location', location);

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

  const url = jobId
    ? `${RAILWAY_API_BASE_URL}/score/jobs/${encodeURIComponent(jobId)}`
    : `${RAILWAY_API_BASE_URL}/score/jobs?${upstreamParams.toString()}`;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), SCORE_PROXY_TIMEOUT_MS);
  const start = Date.now();

  try {
    const upstream = await fetch(url, {
      method: jobId ? 'GET' : 'POST',
      headers: {
        Accept: 'application/json',
        ...(HOMEFIT_PROXY_SECRET ? { 'X-HomeFit-Proxy-Secret': HOMEFIT_PROXY_SECRET } : {}),
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

    // If the upstream is protected by a proxy secret but this proxy isn't configured,
    // return a clear operator-facing message.
    if (upstream.status === 401 && !HOMEFIT_PROXY_SECRET) {
      return NextResponse.json(
        {
          detail:
            'Server misconfigured: set HOMEFIT_PROXY_SECRET (must match backend HOMEFIT_PROXY_SECRET) to enable /api/score.',
        },
        { status: 500, headers: { 'Cache-Control': 'no-store' } }
      );
    }

    // Normalization for job polling:
    // - POST /score/jobs returns {job_id, status}
    // - GET /score/jobs/{id} returns {status, result?}
    // For the frontend we return either:
    // - 202 {job_id, status} when not done yet
    // - 200 <ScoreResponse> when done
    // - propagate errors otherwise
    if (contentType.includes('application/json')) {
      try {
        const parsed = JSON.parse(bodyText);
        if (jobId) {
          const status = parsed?.status;
          if (status === 'done' && parsed?.result) {
            return NextResponse.json(parsed.result, { status: 200, headers: { 'Cache-Control': 'no-store' } });
          }
          if (status === 'queued' || status === 'running') {
            return NextResponse.json(
              { job_id: parsed?.job_id || jobId, status },
              { status: 202, headers: { 'Cache-Control': 'no-store' } }
            );
          }
        } else {
          // Create job response
          if (parsed?.job_id) {
            return NextResponse.json(
              { job_id: parsed.job_id, status: parsed.status || 'queued' },
              { status: 202, headers: { 'Cache-Control': 'no-store' } }
            );
          }
        }
      } catch {
        // fall through
      }
    }

    return new NextResponse(bodyText, {
      status: upstream.status,
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'no-store',
      },
    });
  } catch (err) {
    const durationMs = Date.now() - start;
    const locationHash = md5((location || '').toLowerCase()).slice(0, 10);
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

