import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

const RAILWAY_API_BASE_URL =
  process.env.RAILWAY_API_BASE_URL || 'http://127.0.0.1:8000';

export async function GET() {
  try {
    const upstream = await fetch(`${RAILWAY_API_BASE_URL}/healthz`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });
    const text = await upstream.text();
    return new NextResponse(text, {
      status: upstream.status,
      headers: {
        'Content-Type': upstream.headers.get('content-type') || 'application/json',
        // The version label barely changes: let the CDN answer repeat page loads instead of running a function each time.
        'Cache-Control': upstream.ok ? 'public, s-maxage=300, stale-while-revalidate=3600' : 'no-store',
      },
    });
  } catch {
    return NextResponse.json({ status: 'down' }, { status: 502 });
  }
}

