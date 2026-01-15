import { NextResponse } from 'next/server';

export const runtime = 'nodejs';

const RAILWAY_API_BASE_URL =
  process.env.RAILWAY_API_BASE_URL || 'https://home-fit-production.up.railway.app';

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
        'Cache-Control': 'no-store',
      },
    });
  } catch {
    return NextResponse.json({ status: 'down' }, { status: 502 });
  }
}

