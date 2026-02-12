import { Modal } from './ui/Modal'

interface ConfirmModalProps {
  isOpen: boolean
  message: string
  onClose: () => void
  onConfirm: () => void
}

export function ConfirmModal({ isOpen, message, onClose, onConfirm }: ConfirmModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="Warning"
      confirmText="Confirm"
      variant="danger"
    >
      <div className="flex gap-3 mb-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-error/10">
          <svg className="w-5 h-5 text-error" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
        </div>
        <p className="text-text-secondary text-sm leading-relaxed">{message}</p>
      </div>
    </Modal>
  )
}
