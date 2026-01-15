import { NextRequest, NextResponse } from 'next/server';
import { Ratelimit } from '@upstash/ratelimit';
import { Redis } from '@upstash/redis/cloudflare';

const hasUpstashEnv =
  !!process.env.UPSTASH_REDIS_REST_URL && !!process.env.UPSTASH_REDIS_REST_TOKEN;

// Launch-week defaults. Tune via env without redeploy:
// - HOMEFIT_SCORE_RPM: requests per minute per IP (default 10)
const SCORE_RPM = Number(process.env.HOMEFIT_SCORE_RPM || '10');

const scoreRateLimit = hasUpstashEnv
  ? new Ratelimit({
      redis: Redis.fromEnv(),
      limiter: Ratelimit.slidingWindow(SCORE_RPM, '1 m'),
      analytics: true,
      prefix: 'homefit',
    })
  : null;

function getClientIp(req: NextRequest): string {
  const xff = req.headers.get('x-forwarded-for');
  if (xff) return xff.split(',')[0]?.trim() || 'unknown';
  return req.ip || 'unknown';
}

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Only protect API routes (UI stays fully public).
  if (!pathname.startsWith('/api/')) {
    return NextResponse.next();
  }

  // Only rate limit the expensive endpoints.
  if (pathname !== '/api/score') {
    return NextResponse.next();
  }

  // Fail open when Upstash is not configured (common in local dev).
  if (!scoreRateLimit) {
    return NextResponse.next();
  }

  const ip = getClientIp(req);
  const key = `ip:${ip}:path:${pathname}`;

  try {
    const { success, limit, remaining, reset } = await scoreRateLimit.limit(key);
    if (!success) {
      const retryAfterSeconds = Math.max(0, Math.ceil((reset - Date.now()) / 1000));
      return new NextResponse('Too Many Requests', {
        status: 429,
        headers: {
          'Retry-After': retryAfterSeconds.toString(),
          'X-RateLimit-Limit': limit.toString(),
          'X-RateLimit-Remaining': remaining.toString(),
        },
      });
    }

    const res = NextResponse.next();
    res.headers.set('X-RateLimit-Limit', limit.toString());
    res.headers.set('X-RateLimit-Remaining', remaining.toString());
    return res;
  } catch {
    // If Upstash errors for any reason, do not break scoring.
    return NextResponse.next();
  }
}

export const config = {
  matcher: ['/api/:path*'],
};

