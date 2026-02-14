import { useState, useCallback, useEffect } from 'react'
import { useToast } from 'hooks/useToast'
import { usePool } from 'hooks/usePool'
import { apiCall, importTokenConfig, TokenConfig } from 'lib/api'
import { StatsGrid } from './StatsGrid'
import { MonitorPanel } from './MonitorPanel'
import { TokenTable } from './TokenTable'
import { AddTokenModal } from './AddTokenModal'
import { ConfirmModal } from './ConfirmModal'
import { Toast } from './ui/Toast'
import { LogsPanel } from './logs/LogsPanel'

type TabType = 'pool' | 'logs'

function formatRelativeTime(epochMs: number): string {
  const diff = Date.now() - epochMs
  if (diff < 10000) return 'Just now'
  if (diff < 60000) return `${Math.floor(diff / 1000)}s ago`
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
  return `${Math.floor(diff / 3600000)}h ago`
}

export function App() {
  const { toasts, addToast, removeToast } = useToast()
  const { data, monitorConfig, setMonitorConfig, fallbackConfig, setFallbackConfig, lastSync, refreshData } = usePool()

  const [activeTab, setActiveTab] = useState<TabType>('pool')
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false)
  const [confirmMessage, setConfirmMessage] = useState('')
  const [confirmAction, setConfirmAction] = useState<(() => void) | null>(null)
  const [, setTick] = useState(0)

  // Re-render every 10s to update relative time
  useEffect(() => {
    const interval = setInterval(() => setTick((t) => t + 1), 10000)
    return () => clearInterval(interval)
  }, [])

  const handleAddToken = useCallback(
    async (id: string, csrf: string, session: string) => {
      if (!id || !csrf || !session) {
        addToast('Missing required fields', 'error')
        return
      }

      const resp = await apiCall(
        'add',
        {
          id,
          csrf_token: csrf,
          session_token: session,
        }
      )

      if (resp.status === 'ok') {
        addToast('Token added', 'success')
        setIsAddModalOpen(false)
        refreshData()
      } else {
        addToast(resp.message || 'Error', 'error')
      }
    },
    [addToast, refreshData]
  )

  const handleDeleteToken = useCallback(
    async (id: string) => {
      const resp = await apiCall('remove', { id })
      if (resp.status === 'ok') {
        addToast('Token deleted', 'success')
        refreshData()
      } else {
        addToast(resp.message || 'Error', 'error')
      }
    },
    [addToast, refreshData]
  )

  const handleImportConfig = useCallback(
    async (tokens: TokenConfig[]) => {
      try {
        const resp = await importTokenConfig(tokens)
        if (resp.status === 'ok') {
          addToast(`Imported ${tokens.length} tokens`, 'success')
          setIsAddModalOpen(false)
          refreshData()
        } else {
          addToast(resp.message || 'Import failed', 'error')
        }
      } catch (err) {
        addToast(err instanceof Error ? err.message : 'Import failed', 'error')
      }
    },
    [addToast, refreshData]
  )

  const confirmDelete = useCallback(
    (id: string) => {
      setConfirmMessage(
        `Are you sure you want to permanently delete token "${id}"? This action is irreversible.`
      )
      setConfirmAction(() => () => handleDeleteToken(id))
      setIsConfirmModalOpen(true)
    },
    [handleDeleteToken]
  )

  const executeConfirm = useCallback(() => {
    if (confirmAction) confirmAction()
    setIsConfirmModalOpen(false)
  }, [confirmAction])

  return (
    <div className="min-h-screen text-text-secondary p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <header
          className="mb-6 pb-4 animate-fade-in opacity-0 [animation-fill-mode:forwards]"
          style={{ animationDelay: '0ms' }}
        >
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <span className="inline-block w-2 h-2 rounded-full bg-accent" />
              <h1 className="text-xl font-semibold text-text-primary">Perplexity Token Pool</h1>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-text-muted">
                {lastSync ? formatRelativeTime(lastSync) : 'Syncing...'}
              </span>
              <button
                onClick={refreshData}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-text-muted hover:text-text-secondary hover:bg-elevated transition-colors"
                title="Refresh"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
              <span className={`w-2 h-2 rounded-full ${data.total > 0 ? 'bg-success' : 'bg-text-muted'}`} title={data.total > 0 ? 'Connected' : 'No clients'} />
            </div>
          </div>
          {/* Gradient divider */}
          <div className="mt-4 h-px bg-gradient-to-r from-transparent via-accent/30 to-transparent" />
        </header>

        {/* Tab Navigation */}
        <div
          className="mb-6 animate-fade-in opacity-0 [animation-fill-mode:forwards]"
          style={{ animationDelay: '100ms' }}
        >
          <div className="inline-flex rounded-lg bg-surface border border-border-subtle p-1">
            <button
              onClick={() => setActiveTab('pool')}
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                activeTab === 'pool'
                  ? 'bg-elevated text-text-primary shadow-sm'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              Token Pool
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                activeTab === 'logs'
                  ? 'bg-elevated text-text-primary shadow-sm'
                  : 'text-text-muted hover:text-text-secondary'
              }`}
            >
              Logs
            </button>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'pool' ? (
          <>
            <div
              className="animate-fade-in opacity-0 [animation-fill-mode:forwards]"
              style={{ animationDelay: '150ms' }}
            >
              <StatsGrid data={data} monitorConfig={monitorConfig} />
            </div>

            {monitorConfig && (
              <div
                className="animate-fade-in opacity-0 [animation-fill-mode:forwards]"
                style={{ animationDelay: '200ms' }}
              >
                <MonitorPanel
                  monitorConfig={monitorConfig}
                  onConfigUpdate={setMonitorConfig}
                  onToast={addToast}
                  onRefresh={refreshData}
                />
              </div>
            )}

            <div
              className="animate-fade-in opacity-0 [animation-fill-mode:forwards]"
              style={{ animationDelay: '250ms' }}
            >
              <TokenTable
                clients={data.clients}
                fallbackToAuto={fallbackConfig.fallback_to_auto}
                onToast={addToast}
                onRefresh={refreshData}
                onAddClick={() => setIsAddModalOpen(true)}
                onConfirmDelete={confirmDelete}
                onFallbackChange={(enabled) => setFallbackConfig({ fallback_to_auto: enabled })}
              />
            </div>
          </>
        ) : (
          <div
            className="animate-fade-in opacity-0 [animation-fill-mode:forwards]"
            style={{ animationDelay: '150ms' }}
          >
            <LogsPanel />
          </div>
        )}

        <AddTokenModal
          isOpen={isAddModalOpen}
          onClose={() => setIsAddModalOpen(false)}
          onSubmit={handleAddToken}
          onImportConfig={handleImportConfig}
        />

        <ConfirmModal
          isOpen={isConfirmModalOpen}
          message={confirmMessage}
          onClose={() => setIsConfirmModalOpen(false)}
          onConfirm={executeConfirm}
        />

        {/* Toast container */}
        <div className="fixed bottom-4 right-4 flex flex-col gap-2 z-50">
          {toasts.map((t) => (
            <Toast key={t.id} message={t.message} type={t.type} onClose={() => removeToast(t.id)} />
          ))}
        </div>
      </div>
    </div>
  )
}
