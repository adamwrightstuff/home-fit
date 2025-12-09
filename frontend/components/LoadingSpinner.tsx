export default function LoadingSpinner() {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
      <p className="text-gray-600">Calculating livability score...</p>
      <p className="text-sm text-gray-500 mt-2">This may take 10-15 seconds</p>
    </div>
  )
}
