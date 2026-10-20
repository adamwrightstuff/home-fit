import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const maxDuration = 15;

const RAILWAY_API_BASE_URL =
  process.env.RAILWAY_API_BASE_URL || 'http://127.0.0.1:8000';
const HOMEFIT_PROXY_SECRET = process.env.HOMEFIT_PROXY_SECRET || '';

/** Metro (CBSA) code for a coordinate, for saved places that are not in the catalog. */
export async function GET(req: NextRequest) {
  const lat = req.nextUrl.searchParams.get('lat');
  const lon = req.nextUrl.searchParams.get('lon');
  if (!lat || !lon || Number.isNaN(Number(lat)) || Number.isNaN(Number(lon))) {
    return NextResponse.json({ detail: 'lat and lon are required' }, { status: 400 });
  }
  try {
    const res = await fetch(
      `${RAILWAY_API_BASE_URL}/relocation/metro_for_point?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`,
      {
        headers: {
          Accept: 'application/json',
          ...(HOMEFIT_PROXY_SECRET ? { 'X-HomeFit-Proxy-Secret': HOMEFIT_PROXY_SECRET } : {}),
        },
        cache: 'no-store',
      }
    );
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return NextResponse.json({ detail: 'Metro lookup failed' }, { status: res.status });
    return NextResponse.json(data, { headers: { 'Cache-Control': 'no-store' } });
  } catch {
    return NextResponse.json({ detail: 'Metro lookup is temporarily unavailable.' }, { status: 502 });
  }
}
