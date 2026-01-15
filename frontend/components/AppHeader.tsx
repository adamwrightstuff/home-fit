'use client'

import React from 'react'

interface AppHeaderProps {
  title?: string
  tagline?: string
  children?: React.ReactNode
}

export default function AppHeader({
  title = 'HomeFit',
  tagline = 'Discover how livable any location is across 9 essential factors',
  children,
}: AppHeaderProps) {
  return (
    <header className="hf-header">
      <div style={{ position: 'relative' }}>
        <h1>{title}</h1>
        {tagline ? <p>{tagline}</p> : null}
        {children ? <div style={{ marginTop: '1.5rem' }}>{children}</div> : null}
      </div>
    </header>
  )
}

