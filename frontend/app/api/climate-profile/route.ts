import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const maxDuration = 15;

const RAILWAY_API_BASE_URL = process.env.RAILWAY_API_BASE_URL || 'http://127.0.0.1:8000';
const HOMEFIT_PROXY_SECRET = process.env.HOMEFIT_PROXY_SECRET || '';

export async function GET(req: NextRequest) {
  const lat = req.nextUrl.searchParams.get('lat');
  const lon = req.nextUrl.searchParams.get('lon');
  if (!lat || !lon) {
    return NextResponse.json({ detail: 'Missing lat or lon' }, { status: 400 });
  }

  const url = `${RAILWAY_API_BASE_URL}/climate_profile?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`;
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
    if (!res.ok) return NextResponse.json({}, { status: res.status });
    return NextResponse.json(data, { headers: { 'Cache-Control': 'public, max-age=86400' } });
  } catch {
    return NextResponse.json({}, { status: 502 });
  }
}
