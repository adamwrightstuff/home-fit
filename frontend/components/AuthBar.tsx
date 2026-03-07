'use client'

import React from 'react'
import Link from 'next/link'
import { useAuth } from '@/contexts/AuthContext'
import AuthModal from '@/components/AuthModal'

export default function AuthBar() {
  const { user, loading, isConfigured, signOut, openAuthModal, closeAuthModal, authModalOpen, authModalMode } = useAuth()

  return (
    <>
      <header className="hf-auth-bar">
        <div className="hf-auth-bar-inner">
          <Link href="/" className="hf-auth-bar-logo">
            HomeFit
          </Link>
          <nav className="hf-auth-bar-nav" aria-label="Account">
            {!isConfigured ? (
              <button
                type="button"
                className="hf-auth-bar-btn"
                onClick={() => openAuthModal('signin')}
                title="Sign in (configure Supabase env to enable)"
              >
                Sign in
              </button>
            ) : loading ? (
              <span className="hf-auth-bar-muted">Loading…</span>
            ) : user ? (
              <>
                <Link href="/saved" className="hf-auth-bar-btn" style={{ textDecoration: 'none' }}>
                  My places
                </Link>
                <span className="hf-auth-bar-email" title={user.email ?? undefined}>
                  {user.email}
                </span>
                <button
                  type="button"
                  className="hf-auth-bar-btn"
                  onClick={() => signOut()}
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
                >
                  Sign in
                </button>
                <button
                  type="button"
                  className="hf-auth-bar-btn hf-auth-bar-btn-primary"
                  onClick={() => openAuthModal('signup')}
                >
                  Sign up
                </button>
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
