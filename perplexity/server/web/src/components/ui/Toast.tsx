import { useEffect } from 'react'

interface ToastProps {
  message: string
  type: 'success' | 'error'
  onClose: () => void
}

export function Toast({ message, type, onClose }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000)
    return () => clearTimeout(timer)
  }, [onClose])

  const styles = type === 'success'
    ? { bg: 'bg-success/10', border: 'border-success/20', text: 'text-success' }
    : { bg: 'bg-error/10', border: 'border-error/20', text: 'text-error' }

  return (
    <div className={`${styles.bg} border ${styles.border} rounded-lg px-4 py-3 text-sm font-medium shadow-lg animate-slide-in-right overflow-hidden`}>
      <div className="flex items-center gap-2.5">
        {type === 'success' ? (
          <svg className={`w-4 h-4 shrink-0 ${styles.text}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        ) : (
          <svg className={`w-4 h-4 shrink-0 ${styles.text}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        )}
        <span className={styles.text}>{message}</span>
      </div>
      <div className={`absolute bottom-0 left-0 h-0.5 ${styles.text} opacity-30 animate-progress-shrink`} />
    </div>
  )
}
