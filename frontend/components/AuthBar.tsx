'use client'

import React, { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'
import AuthModal from '@/components/AuthModal'

export default function AuthBar() {
  const { user, loading, isConfigured, signOut, openAuthModal, closeAuthModal, authModalOpen, authModalMode } = useAuth()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const pathname = usePathname() ?? ''
  // Two modes, one switch: travel pages are under /vacation, everything else is HomeFit.
  const travelMode = pathname.startsWith('/vacation')
  const searchHref = travelMode ? '/vacation' : '/search'
  const headerRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const el = headerRef.current
    if (!el) return
    const update = () => document.documentElement.style.setProperty('--authbar-h', `${el.offsetHeight}px`)
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const closeMobileMenu = () => setMobileMenuOpen(false)

  const accountNav = !isConfigured ? (
    <button
      type="button"
      className="hf-auth-bar-btn"
      onClick={() => { openAuthModal('signin'); closeMobileMenu() }}
      title="Sign in (configure Supabase env to enable)"
      style={{ color: '#1a1a2e' }}
    >
      Sign in
    </button>
  ) : loading ? (
    <span className="hf-auth-bar-muted" style={{ color: '#5a5a6e' }}>…</span>
  ) : user ? (
    <>
      <Link href="/saved" className="hf-auth-bar-btn" style={{ textDecoration: 'none', color: '#1a1a2e' }} onClick={closeMobileMenu}>
        My places
      </Link>
      <Link href="/profile" className="hf-auth-bar-btn" style={{ textDecoration: 'none', color: '#1a1a2e' }} onClick={closeMobileMenu}>
        Profile
      </Link>
      <button
        type="button"
        className="hf-auth-bar-btn"
        onClick={() => { signOut(); closeMobileMenu() }}
        style={{ color: '#1a1a2e' }}
      >
        Sign out
      </button>
    </>
  ) : (
    <>
      <button
        type="button"
        className="hf-auth-bar-btn"
        onClick={() => { openAuthModal('signin'); closeMobileMenu() }}
        style={{ color: '#1a1a2e' }}
      >
        Sign in
      </button>
      <button
        type="button"
        className="hf-auth-bar-btn hf-auth-bar-btn-primary"
        onClick={() => { openAuthModal('signup'); closeMobileMenu() }}
        style={{ color: '#fff' }}
      >
        Sign up
      </button>
    </>
  )

  return (
    <>
      <header ref={headerRef} className="hf-auth-bar" style={{ position: 'relative' }}>
        <div className="hf-auth-bar-inner">
          <Link href="/" className="hf-auth-bar-logo">
            Trovamo
          </Link>

          {/* Middle nav — hidden on mobile, visible md+ */}
          <nav className="hf-auth-bar-nav hidden md:flex" aria-label="Main" style={{ alignItems: 'center', gap: '0.75rem' }}>
            {/* Mode switch: one control, two options (Airbnb style) */}
            <div role="group" aria-label="Mode" style={{ display: 'inline-flex', background: '#F3F4F6', borderRadius: 999, padding: 3 }}>
              <Link
                href="/catalog"
                aria-current={!travelMode ? 'page' : undefined}
                style={{ textDecoration: 'none', borderRadius: 999, padding: '0.3rem 0.9rem', fontSize: '0.875rem', fontWeight: 600, color: !travelMode ? '#1a1a2e' : '#6B7280', background: !travelMode ? '#fff' : 'transparent', boxShadow: !travelMode ? '0 1px 2px rgba(0,0,0,0.12)' : 'none' }}
              >
                HomeFit
              </Link>
              <Link
                href="/vacation/explorer"
                aria-current={travelMode ? 'page' : undefined}
                style={{ textDecoration: 'none', borderRadius: 999, padding: '0.3rem 0.9rem', fontSize: '0.875rem', fontWeight: 600, color: travelMode ? '#92400E' : '#6B7280', background: travelMode ? '#fff' : 'transparent', boxShadow: travelMode ? '0 1px 2px rgba(0,0,0,0.12)' : 'none' }}
              >
                TravelFit
              </Link>
            </div>
            <Link href={searchHref} className="hf-auth-bar-btn" style={{ textDecoration: 'none', color: '#1a1a2e', fontSize: '0.875rem' }}>
              Search any place
            </Link>
          </nav>

          {/* Desktop account nav — hidden on mobile */}
          <nav className="hf-auth-bar-account-desktop hidden md:flex" aria-label="Account">
            {accountNav}
          </nav>

          {/* Mobile hamburger — hidden on desktop */}
          <button
            type="button"
            className="hf-auth-bar-menu-toggle flex md:hidden"
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileMenuOpen}
            onClick={() => setMobileMenuOpen(v => !v)}
          >
            {mobileMenuOpen ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                <line x1="3" y1="6" x2="21" y2="6"/>
                <line x1="3" y1="12" x2="21" y2="12"/>
                <line x1="3" y1="18" x2="21" y2="18"/>
              </svg>
            )}
          </button>
        </div>

        {/* Mobile dropdown */}
        <nav className={`hf-auth-bar-mobile-menu${mobileMenuOpen ? ' open' : ''}`} aria-label="Mobile menu">
          <Link href="/catalog" className="hf-auth-bar-btn" aria-current={!travelMode ? 'page' : undefined} style={{ textDecoration: 'none', color: '#1a1a2e', fontWeight: !travelMode ? 700 : 500 }} onClick={closeMobileMenu}>
            HomeFit
          </Link>
          <Link href="/vacation/explorer" className="hf-auth-bar-btn" aria-current={travelMode ? 'page' : undefined} style={{ textDecoration: 'none', color: '#92400E', fontWeight: travelMode ? 700 : 500 }} onClick={closeMobileMenu}>
            TravelFit
          </Link>
          <Link href={searchHref} className="hf-auth-bar-btn" style={{ textDecoration: 'none', color: '#1a1a2e', fontSize: '0.9rem' }} onClick={closeMobileMenu}>
            Search any place
          </Link>
          {accountNav}
        </nav>
      </header>
      <AuthModal
        isOpen={authModalOpen}
        onClose={closeAuthModal}
        initialMode={authModalMode}
      />
    </>
  )
}
