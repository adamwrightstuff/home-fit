'use client'

import { useState, useEffect } from 'react'

export default function ApiVersion() {
  const [version, setVersion] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    // Ask once per browser session; the response is also cached at the CDN (see app/api/health/route.ts).
    try {
      const cached = sessionStorage.getItem('homefit_api_version')
      if (cached) { setVersion(cached); return }
    } catch { /* storage unavailable */ }
    fetch('/api/health')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data?.version) {
          setVersion(data.version)
          try { sessionStorage.setItem('homefit_api_version', String(data.version)) } catch { /* ignore */ }
        }
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  if (!version) return null

  return (
    <span
      className="tr-muted"
      style={{
        fontSize: '0.75rem',
        opacity: 0.85,
        letterSpacing: '0.02em',
      }}
      title="Backend API version"
    >
      API {version}
    </span>
  )
}
