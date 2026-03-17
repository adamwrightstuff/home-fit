import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';

const RAILWAY_API_BASE_URL =
  process.env.RAILWAY_API_BASE_URL || 'http://127.0.0.1:8000';
const HOMEFIT_PROXY_SECRET = process.env.HOMEFIT_PROXY_SECRET || '';

export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { detail: 'Invalid JSON body' },
      { status: 400 }
    );
  }

  const url = `${RAILWAY_API_BASE_URL}/score/recompute_composites`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };
  if (HOMEFIT_PROXY_SECRET) {
    headers['X-HomeFit-Proxy-Secret'] = HOMEFIT_PROXY_SECRET;
  }

  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    cache: 'no-store',
  });

  const text = await res.text();
  const contentType = res.headers.get('content-type') || 'application/json';
  if (!res.ok) {
    let detail = 'Recompute failed';
    try {
      if (contentType.includes('application/json')) {
        const parsed = JSON.parse(text);
        if (parsed && typeof parsed.detail === 'string') detail = parsed.detail;
      } else if (text) detail = text.slice(0, 200);
    } catch {
      /* use default */
    }
    return NextResponse.json(
      { detail },
      { status: res.status === 401 ? 500 : res.status, headers: { 'Cache-Control': 'no-store' } }
    );
  }

  let data: unknown;
  try {
    data = contentType.includes('application/json') ? JSON.parse(text) : { raw: text };
  } catch {
    return NextResponse.json(
      { detail: 'Invalid JSON from backend' },
      { status: 502, headers: { 'Cache-Control': 'no-store' } }
    );
  }

  return NextResponse.json(data, {
    headers: { 'Cache-Control': 'no-store' },
  });
}
