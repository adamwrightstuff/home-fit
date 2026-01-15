interface ErrorMessageProps {
  message: string
}

export default function ErrorMessage({ message }: ErrorMessageProps) {
  return (
    <div className="hf-error">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <svg width="20" height="20" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
        </svg>
        <p style={{ fontWeight: 700, margin: 0 }}>Error</p>
      </div>
      <p style={{ marginTop: '0.75rem', marginBottom: 0 }}>{message}</p>
    </div>
  )
}
