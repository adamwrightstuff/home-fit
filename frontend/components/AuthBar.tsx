'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/contexts/AuthContext'
import AuthModal from '@/components/AuthModal'

export default function AuthBar() {
  const { user, loading, isConfigured, signOut, openAuthModal, closeAuthModal, authModalOpen, authModalMode } = useAuth()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

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
      <header className="hf-auth-bar" style={{ position: 'relative' }}>
        <div className="hf-auth-bar-inner">
          <Link href="/" className="hf-auth-bar-logo">
            Trovamo
          </Link>

          {/* Middle nav — hidden on mobile, visible md+ */}
          <nav className="hf-auth-bar-nav hidden md:flex" aria-label="Main">
            <Link href="/catalog" className="hf-auth-bar-btn" style={{ textDecoration: 'none', color: '#1a1a2e' }}>
              Explore
            </Link>
            <Link
              href="/search"
              className="hf-auth-bar-btn"
              style={{
                textDecoration: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.3rem',
                padding: '3px 10px',
                borderRadius: 999,
                border: '1px solid #B5D4F4',
                color: '#185FA5',
                background: '#E6F1FB',
                fontWeight: 600,
                fontSize: '0.85rem',
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="10"/>
                <line x1="2" y1="12" x2="22" y2="12"/>
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
              </svg>
              Search anywhere
            </Link>
          </nav>

          {/* Desktop account nav */}
          <nav className="hf-auth-bar-account-desktop" aria-label="Account">
            {accountNav}
          </nav>

          {/* Mobile hamburger */}
          <button
            type="button"
            className="hf-auth-bar-menu-toggle"
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
          <Link href="/catalog" className="hf-auth-bar-btn" style={{ textDecoration: 'none', color: '#1a1a2e' }} onClick={closeMobileMenu}>
            Explore
          </Link>
          <Link
            href="/search"
            className="hf-auth-bar-btn"
            style={{ textDecoration: 'none', color: '#185FA5' }}
            onClick={closeMobileMenu}
          >
            Search anywhere
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
