'use client'

import { useState, useEffect } from 'react'

export default function ApiVersion() {
  const [version, setVersion] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch('/api/health', { cache: 'no-store' })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data?.version) setVersion(data.version)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [])

  if (!version) return null

  return (
    <span
      className="hf-muted"
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
