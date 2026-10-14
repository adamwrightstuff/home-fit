'use client'

import { useEffect, useState } from 'react'

interface WikiPhotoResult {
  src: string
  caption: string | null
}

async function fetchWikipediaPhoto(name: string, state: string | null): Promise<WikiPhotoResult | null> {
  const query = state ? `${name}, ${state}` : name
  const url = `https://en.wikipedia.org/w/api.php?action=query&titles=${encodeURIComponent(query)}&prop=pageimages&format=json&pithumbsize=1200&origin=*`
  try {
    const res = await fetch(url)
    if (!res.ok) return null
    const data = await res.json()
    const pages = data?.query?.pages ?? {}
    const page = Object.values(pages)[0] as Record<string, unknown>
    const thumb = page?.thumbnail as { source?: string } | undefined
    if (!thumb?.source) return null
    return { src: thumb.source, caption: `${query} via Wikipedia` }
  } catch {
    return null
  }
}

export default function NeighborhoodPhoto({
  name,
  state,
}: {
  name: string
  state: string | null
}) {
  const [photo, setPhoto] = useState<WikiPhotoResult | null>(null)
  const [status, setStatus] = useState<'loading' | 'found' | 'none'>('loading')

  useEffect(() => {
    let cancelled = false
    fetchWikipediaPhoto(name, state).then((result) => {
      if (cancelled) return
      if (result) {
        setPhoto(result)
        setStatus('found')
      } else {
        setStatus('none')
      }
    })
    return () => { cancelled = true }
  }, [name, state])

  if (status !== 'found' || !photo) return null

  return (
    <div
      className="mb-6 overflow-hidden rounded-2xl"
      style={{ position: 'relative', width: '100%', aspectRatio: '16/7' }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={photo.src}
        alt={`${name} neighborhood photo`}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          display: 'block',
        }}
        loading="lazy"
      />
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          right: 0,
          padding: '4px 8px',
          fontSize: 10,
          color: 'rgba(255,255,255,0.6)',
          background: 'rgba(0,0,0,0.35)',
          borderTopLeftRadius: 6,
        }}
      >
        {photo.caption}
      </div>
    </div>
  )
}
