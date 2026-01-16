'use client'

import React from 'react'
import Image from 'next/image'

interface AppHeaderProps {
  title?: string
  tagline?: string
  heroImageUrl?: string
  heroImageAlt?: string
  children?: React.ReactNode
}

export default function AppHeader({
  title = 'HomeFit',
  tagline = 'Find the neighborhood where you truly belong',
  heroImageUrl,
  heroImageAlt = 'Neighborhood streetscape',
  children,
}: AppHeaderProps) {
  return (
    <header className="hf-header">
      <div className={heroImageUrl ? 'hf-hero-grid' : ''} style={{ position: 'relative' }}>
        <div className={heroImageUrl ? 'hf-hero-text' : ''}>
          <h1>{title}</h1>
          {tagline ? <p>{tagline}</p> : null}
          {children ? <div style={{ marginTop: '1.5rem' }}>{children}</div> : null}
        </div>

        {heroImageUrl ? (
          <div className="hf-hero-imageWrap">
            <Image
              className="hf-hero-image"
              src={heroImageUrl}
              alt={heroImageAlt}
              width={800}
              height={500}
              priority
              sizes="(max-width: 768px) 100vw, 560px"
              style={{ objectFit: 'cover' }}
            />
          </div>
        ) : null}
      </div>
    </header>
  )
}

