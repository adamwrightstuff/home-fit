'use client'

import React, { useState } from 'react'
import Link from 'next/link'
import { useAuth } from '@/contexts/AuthContext'
import AuthModal from '@/components/AuthModal'

export default function AuthBar() {
  const { user, loading, isConfigured, signOut, openAuthModal, closeAuthModal, authModalOpen, authModalMode } = useAuth()
  const [signupTooltipVisible, setSignupTooltipVisible] = useState(false)

  return (
    <>
      <header className="hf-auth-bar">
        <div className="hf-auth-bar-inner">
          <Link href="/" className="hf-auth-bar-logo">
            Trovamo
          </Link>
          <nav className="hf-auth-bar-nav" aria-label="Main">
            <Link href="/catalog" className="hf-auth-bar-btn" style={{ textDecoration: 'none', color: '#1a1a2e' }}>
              Explore
            </Link>
            <Link href="/search" className="hf-auth-bar-btn" style={{ textDecoration: 'none', color: '#1a1a2e', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              Search
              <span style={{ fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', padding: '1px 4px', borderRadius: 3, background: 'var(--hf-primary-1)', color: '#fff' }}>Beta</span>
            </Link>
          </nav>
          <nav className="hf-auth-bar-nav" aria-label="Account">
            {!isConfigured ? (
              <button
                type="button"
                className="hf-auth-bar-btn"
                onClick={() => openAuthModal('signin')}
                title="Sign in (configure Supabase env to enable)"
                style={{ color: '#1a1a2e' }}
              >
                Sign in
              </button>
            ) : loading ? (
              <span className="hf-auth-bar-muted" style={{ color: '#5a5a6e' }}>Loading…</span>
            ) : user ? (
              <>
                <Link href="/saved" className="hf-auth-bar-btn" style={{ textDecoration: 'none', color: '#1a1a2e' }}>
                  My places
                </Link>
                <span className="hf-auth-bar-email" title={user.email ?? undefined} style={{ color: '#5a5a6e' }}>
                  {user.email}
                </span>
                <button
                  type="button"
                  className="hf-auth-bar-btn"
                  onClick={() => signOut()}
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
                  onClick={() => openAuthModal('signin')}
                  style={{ color: '#1a1a2e' }}
                >
                  Sign in
                </button>
                <div style={{ position: 'relative', display: 'inline-block' }}>
                  {signupTooltipVisible && (
                    <div
                      style={{
                        position: 'absolute',
                        bottom: 'calc(100% + 8px)',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        background: '#1a1a2e',
                        color: '#fff',
                        fontSize: 11,
                        borderRadius: 6,
                        padding: '5px 9px',
                        whiteSpace: 'nowrap',
                        pointerEvents: 'none',
                        zIndex: 100,
                        boxShadow: '0 2px 8px rgba(0,0,0,0.18)',
                      }}
                    >
                      Save neighborhoods · Adjust weights · Get score alerts
                      <div
                        style={{
                          position: 'absolute',
                          top: '100%',
                          left: '50%',
                          transform: 'translateX(-50%)',
                          borderLeft: '5px solid transparent',
                          borderRight: '5px solid transparent',
                          borderTop: '5px solid #1a1a2e',
                        }}
                      />
                    </div>
                  )}
                  <button
                    type="button"
                    className="hf-auth-bar-btn hf-auth-bar-btn-primary"
                    onClick={() => openAuthModal('signup')}
                    onMouseEnter={() => setSignupTooltipVisible(true)}
                    onMouseLeave={() => setSignupTooltipVisible(false)}
                    style={{ color: '#fff' }}
                  >
                    Sign up
                  </button>
                </div>
              </>
            )}
          </nav>
        </div>
      </header>
      <AuthModal
        isOpen={authModalOpen}
        onClose={closeAuthModal}
        initialMode={authModalMode}
      />
    </>
  )
}
