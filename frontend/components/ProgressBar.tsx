'use client'

interface ProgressBarProps {
  progress: number
}

export default function ProgressBar({ progress }: ProgressBarProps) {
  const clamped_progress = Math.min(100, Math.max(0, progress))
  
  return (
    <div className="w-full mb-6">
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm font-medium text-homefit-text-primary">Progress</span>
        <span className="text-sm font-medium text-homefit-text-primary">{clamped_progress.toFixed(0)}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
        <div
          className="h-full bg-homefit-accent-primary transition-all duration-300 ease-out rounded-full"
          style={{ width: `${clamped_progress}%` }}
        >
          <div className="h-full w-full bg-gradient-to-r from-homefit-accent-primary/80 to-homefit-accent-primary animate-pulse"></div>
        </div>
      </div>
    </div>
  )
}
