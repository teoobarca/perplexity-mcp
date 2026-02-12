import { useState, useRef } from 'react'
import { Modal } from './ui/Modal'
import { TokenConfig } from 'lib/api'

interface AddTokenModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (id: string, csrf: string, session: string) => void
  onImportConfig?: (tokens: TokenConfig[]) => void
}

export function AddTokenModal({ isOpen, onClose, onSubmit, onImportConfig }: AddTokenModalProps) {
  const [form, setForm] = useState({ id: '', csrf: '', session: '' })
  const [mode, setMode] = useState<'manual' | 'upload'>('manual')
  const [uploadedTokens, setUploadedTokens] = useState<TokenConfig[] | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = () => {
    if (mode === 'upload' && uploadedTokens && onImportConfig) {
      onImportConfig(uploadedTokens)
      resetForm()
    } else if (mode === 'manual' && form.id && form.csrf && form.session) {
      onSubmit(form.id, form.csrf, form.session)
      resetForm()
    }
  }

  const resetForm = () => {
    setForm({ id: '', csrf: '', session: '' })
    setMode('manual')
    setUploadedTokens(null)
    setUploadError(null)
  }

  const handleClose = () => {
    resetForm()
    onClose()
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploadError(null)
    const reader = new FileReader()
    reader.onload = (event) => {
      try {
        const content = event.target?.result as string
        const parsed = JSON.parse(content)

        let tokens: TokenConfig[]
        if (Array.isArray(parsed)) {
          tokens = parsed
        } else if (parsed.tokens && Array.isArray(parsed.tokens)) {
          tokens = parsed.tokens
        } else {
          throw new Error('Invalid format: expected array of tokens')
        }

        for (const token of tokens) {
          if (!token.id || !token.csrf_token || !token.session_token) {
            throw new Error('Invalid token entry: missing required fields (id, csrf_token, session_token)')
          }
        }

        setUploadedTokens(tokens)
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : 'Failed to parse config file')
        setUploadedTokens(null)
      }
    }
    reader.onerror = () => {
      setUploadError('Failed to read file')
      setUploadedTokens(null)
    }
    reader.readAsText(file)
  }

  const isSubmitDisabled = mode === 'upload'
    ? !uploadedTokens || !onImportConfig
    : !form.id || !form.csrf || !form.session

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      onConfirm={handleSubmit}
      title="Add Token"
      confirmText={mode === 'upload' ? 'Import Config' : 'Add Token'}
      variant="primary"
      confirmDisabled={isSubmitDisabled}
    >
      <div className="space-y-5">
        {/* Mode Toggle */}
        <div className="flex gap-1 p-1 bg-elevated rounded-lg border border-border-subtle">
          <button
            onClick={() => setMode('manual')}
            className={`flex-1 px-3 py-1.5 text-sm rounded-md transition-all ${
              mode === 'manual'
                ? 'bg-accent/15 text-accent font-medium'
                : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            Manual Input
          </button>
          <button
            onClick={() => setMode('upload')}
            className={`flex-1 px-3 py-1.5 text-sm rounded-md transition-all ${
              mode === 'upload'
                ? 'bg-accent/15 text-accent font-medium'
                : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            Upload Config
          </button>
        </div>

        {mode === 'manual' ? (
          <>
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1.5">Identifier</label>
              <input
                type="text"
                placeholder="e.g. main"
                value={form.id}
                onChange={(e) => setForm({ ...form, id: e.target.value })}
                className="w-full bg-elevated border border-border rounded-lg p-3 text-text-primary text-sm focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors placeholder-text-muted"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1.5">CSRF Token</label>
              <textarea
                rows={2}
                placeholder="Enter CSRF token..."
                value={form.csrf}
                onChange={(e) => setForm({ ...form, csrf: e.target.value })}
                className="w-full bg-elevated border border-border rounded-lg p-3 text-text-primary text-sm focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors placeholder-text-muted font-mono text-xs"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1.5">Session Token</label>
              <textarea
                rows={3}
                placeholder="Enter session token..."
                value={form.session}
                onChange={(e) => setForm({ ...form, session: e.target.value })}
                className="w-full bg-elevated border border-border rounded-lg p-3 text-text-primary text-sm focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors placeholder-text-muted font-mono text-xs"
              />
            </div>
          </>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-text-muted mb-1.5">Upload Config File (JSON)</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                onChange={handleFileUpload}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full bg-elevated border-2 border-dashed border-border rounded-xl p-8 text-text-muted text-sm hover:border-accent/50 hover:text-accent transition-colors flex flex-col items-center gap-2"
              >
                <svg className="w-8 h-8 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" />
                </svg>
                {uploadedTokens ? (
                  <span className="text-accent">
                    Config loaded: {uploadedTokens.length} token(s)
                  </span>
                ) : (
                  'Click to select tokens.json'
                )}
              </button>
            </div>

            {uploadError && (
              <div className="bg-error/10 border border-error/20 rounded-lg p-3 text-error text-xs">
                Error: {uploadError}
              </div>
            )}

            {uploadedTokens && (
              <div className="bg-elevated border border-border rounded-lg p-4 text-xs space-y-2">
                <div className="text-text-secondary">
                  <span className="text-accent">Tokens:</span> {uploadedTokens.length}
                </div>
                <div className="text-text-muted mt-2 pt-2 border-t border-border-subtle font-mono">
                  IDs: {uploadedTokens.map(t => t.id).join(', ')}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}
