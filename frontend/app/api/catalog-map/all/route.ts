import { CACHE_HEADERS, buildAllPayload } from '@/lib/catalogMapServer'

// Not force-static: the list is about 40 MB of JSON, and a prerendered output that large risks Vercel's deployment
// size limits. Instead the response is serialized once per server instance and cached at the CDN for a day, so the
// catalog files are parsed and stringified at most once per warm instance and repeat visits never reach a function.
export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'

let cachedBody: string | null = null

export async function GET() {
  if (!cachedBody) {
    const { body, found } = buildAllPayload()
    if (!found) return Response.json(body)
    cachedBody = JSON.stringify(body)
  }
  return new Response(cachedBody, { headers: { 'Content-Type': 'application/json', ...CACHE_HEADERS } })
}
