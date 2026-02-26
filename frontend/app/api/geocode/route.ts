import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const maxDuration = 15;

const RAILWAY_API_BASE_URL =
  process.env.RAILWAY_API_BASE_URL || 'https://home-fit-production.up.railway.app';
const HOMEFIT_PROXY_SECRET = process.env.HOMEFIT_PROXY_SECRET || '';

export async function GET(req: NextRequest) {
  const location = req.nextUrl.searchParams.get('location')?.trim();
  if (!location) {
    return NextResponse.json({ detail: 'Missing required query param: location' }, { status: 400 });
  }

  const url = `${RAILWAY_API_BASE_URL}/geocode?location=${encodeURIComponent(location)}`;
  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        ...(HOMEFIT_PROXY_SECRET ? { 'X-HomeFit-Proxy-Secret': HOMEFIT_PROXY_SECRET } : {}),
      },
      cache: 'no-store',
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail =
        typeof data?.detail === 'string'
          ? data.detail
          : res.status === 502 || res.status === 503
            ? 'Location service is temporarily unavailable. Please try again in a moment.'
            : 'Geocode failed';
      return NextResponse.json({ detail }, { status: res.status });
    }
    return NextResponse.json(data, { headers: { 'Cache-Control': 'no-store' } });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { detail: msg?.trim() ? msg : 'Location service is temporarily unavailable. Please try again in a moment.' },
      { status: 502 }
    );
  }
}
