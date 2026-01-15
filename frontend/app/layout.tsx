import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'HomeFit - Livability Score',
  description: 'Discover how livable any location is across 9 essential factors',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
