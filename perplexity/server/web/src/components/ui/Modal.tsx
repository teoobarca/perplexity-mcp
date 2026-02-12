import { ReactNode } from 'react'

interface ModalProps {
  isOpen: boolean
  title: string
  children: ReactNode
  onClose: () => void
  onConfirm: () => void
  confirmText?: string
  variant?: 'primary' | 'danger'
  confirmDisabled?: boolean
}

export function Modal({
  isOpen,
  title,
  children,
  onClose,
  onConfirm,
  confirmText = 'Confirm',
  variant = 'primary',
  confirmDisabled = false,
}: ModalProps) {
  if (!isOpen) return null

  const confirmClass = variant === 'danger'
    ? 'bg-error text-white hover:bg-red-600'
    : 'bg-accent text-white hover:bg-accent-hover'

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex justify-center items-center" onClick={onClose}>
      <div
        className="bg-surface border border-border rounded-xl w-full max-w-lg mx-4 p-6 animate-scale-in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-text-primary">{title}</h3>
          <button
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-text-muted hover:text-text-secondary hover:bg-elevated transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M1 1l12 12M13 1L1 13" />
            </svg>
          </button>
        </div>
        <div className="text-text-secondary">{children}</div>
        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border border-border text-text-secondary hover:bg-elevated transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={confirmDisabled}
            className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${confirmClass} ${
              confirmDisabled ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
