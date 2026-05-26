import type { Metadata, Viewport } from 'next'
import './globals.css'
import ClientLayout from '@/components/ClientLayout'

export const metadata: Metadata = {
  title: 'Trovamo — We find your place.',
  description: 'Score any neighborhood against what matters most to you. Trovamo measures 13 pillars of livability to help you find where you actually belong.',
  openGraph: {
    title: 'Trovamo — We find your place.',
    description: 'Score any neighborhood against what matters most to you.',
    url: 'https://www.trovamo.co',
    siteName: 'Trovamo',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Trovamo — We find your place.',
    description: 'Score any neighborhood against what matters most to you.',
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  )
}
