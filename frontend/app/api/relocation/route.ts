import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const maxDuration = 15;

const RAILWAY_API_BASE_URL =
  process.env.RAILWAY_API_BASE_URL || 'http://127.0.0.1:8000';
const HOMEFIT_PROXY_SECRET = process.env.HOMEFIT_PROXY_SECRET || '';

const PARAMS = [
  'origin_metro', 'dest_metro', 'income', 'monthly_cost',
  'origin_state', 'dest_state', 'origin_city', 'dest_city',
] as const;

/** Income needed in dest_metro to keep the same money left over as in origin_metro (estimate). */
export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams;
  for (const k of ['origin_metro', 'dest_metro', 'income'] as const) {
    if (!q.get(k)) return NextResponse.json({ detail: `Missing required query param: ${k}` }, { status: 400 });
  }
  const out = new URLSearchParams();
  for (const k of PARAMS) {
    const v = q.get(k)?.trim();
    if (v) out.set(k, v);
  }
  try {
    const res = await fetch(`${RAILWAY_API_BASE_URL}/relocation/equivalent?${out}`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        ...(HOMEFIT_PROXY_SECRET ? { 'X-HomeFit-Proxy-Secret': HOMEFIT_PROXY_SECRET } : {}),
      },
      cache: 'no-store',
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      return NextResponse.json(
        { detail: typeof data?.detail === 'string' ? data.detail : 'Cost estimate unavailable' },
        { status: res.status }
      );
    }
    return NextResponse.json(data, { headers: { 'Cache-Control': 'no-store' } });
  } catch {
    return NextResponse.json({ detail: 'Cost estimate is temporarily unavailable.' }, { status: 502 });
  }
}
