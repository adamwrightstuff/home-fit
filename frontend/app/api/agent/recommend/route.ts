import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';
export const maxDuration = 60;

const RAILWAY_API_BASE_URL =
  process.env.RAILWAY_API_BASE_URL || 'http://127.0.0.1:8000';
const HOMEFIT_PROXY_SECRET = process.env.HOMEFIT_PROXY_SECRET || '';

export async function POST(req: NextRequest) {
  const body = await req.text();
  const start = Date.now();

  try {
    const upstream = await fetch(`${RAILWAY_API_BASE_URL}/agent/recommend`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...(HOMEFIT_PROXY_SECRET ? { 'X-HomeFit-Proxy-Secret': HOMEFIT_PROXY_SECRET } : {}),
      },
      body,
      cache: 'no-store',
    });

    const bodyText = await upstream.text();
    const contentType = upstream.headers.get('content-type') || 'application/json';

    if (upstream.status === 401 && !HOMEFIT_PROXY_SECRET) {
      return NextResponse.json(
        {
          detail:
            'Server misconfigured: set HOMEFIT_PROXY_SECRET (must match backend HOMEFIT_PROXY_SECRET) to enable /api/agent/recommend.',
        },
        { status: 500, headers: { 'Cache-Control': 'no-store' } }
      );
    }

    console.log(
      JSON.stringify({
        msg: 'proxy_agent_recommend',
        status: upstream.status,
        duration_ms: Date.now() - start,
      })
    );

    return new NextResponse(bodyText, {
      status: upstream.status,
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'no-store',
      },
    });
  } catch (err) {
    const errMsg = err instanceof Error ? err.message : String(err);
    console.log(
      JSON.stringify({
        msg: 'proxy_agent_recommend_error',
        duration_ms: Date.now() - start,
        error: errMsg,
      })
    );
    return NextResponse.json(
      { detail: 'Upstream request failed or timed out', error: errMsg },
      { status: 502, headers: { 'Cache-Control': 'no-store' } }
    );
  }
}
