interface ErrorMessageProps {
  message: string
}

export default function ErrorMessage({ message }: ErrorMessageProps) {
  return (
    <div className="bg-homefit-error/10 border border-homefit-error/30 rounded-lg p-4">
      <div className="flex items-center">
        <svg className="w-5 h-5 text-homefit-error mr-2" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
        </svg>
        <p className="text-homefit-error font-semibold">Error</p>
      </div>
      <p className="text-homefit-error mt-2">{message}</p>
    </div>
  )
}
