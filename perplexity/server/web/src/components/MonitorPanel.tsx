import { useState } from 'react'
import { MonitorConfig, updateMonitorConfig, apiCall } from 'lib/api'
import { Toggle } from './ui/Toggle'

interface MonitorPanelProps {
  monitorConfig: MonitorConfig
  onConfigUpdate: (config: MonitorConfig) => void
  onToast: (message: string, type: 'success' | 'error') => void
  onRefresh: () => void
}

export function MonitorPanel({
  monitorConfig,
  onConfigUpdate,
  onToast,
  onRefresh,
}: MonitorPanelProps) {
  const [isConfigOpen, setIsConfigOpen] = useState(false)
  const [isGlobalTesting, setIsGlobalTesting] = useState(false)
  const [configForm, setConfigForm] = useState({
    enable: monitorConfig.enable,
    interval: monitorConfig.interval,
    tg_bot_token: monitorConfig.tg_bot_token,
    tg_chat_id: monitorConfig.tg_chat_id,
  })

  const handleMonitorAction = async (action: string) => {
    if (action === 'test') {
      setIsGlobalTesting(true)
    }

    try {
      const resp = await apiCall(`monitor/${action}`, {})
      if (resp.status === 'ok') {
        onToast(`Monitor ${action} completed`, 'success')
        onRefresh()
      } else {
        onToast(resp.message || 'Error', 'error')
      }
    } finally {
      if (action === 'test') {
        setIsGlobalTesting(false)
      }
    }
  }

  const handleToggleEnable = async (enabled: boolean) => {
    try {
      const resp = await updateMonitorConfig({ ...configForm, enable: enabled })
      if (resp.status === 'ok' && resp.config) {
        onConfigUpdate(resp.config)
        setConfigForm((f) => ({ ...f, enable: enabled }))
        onToast(enabled ? 'Monitor enabled' : 'Monitor disabled', 'success')
      } else {
        onToast(resp.message || 'Failed', 'error')
      }
    } catch {
      onToast('Failed to update', 'error')
    }
  }

  const handleSaveConfig = async () => {
    try {
      const resp = await updateMonitorConfig(configForm)
      if (resp.status === 'ok' && resp.config) {
        onToast('Config saved', 'success')
        onConfigUpdate(resp.config)
        setIsConfigOpen(false)
      } else {
        onToast(resp.message || 'Save failed', 'error')
      }
    } catch {
      onToast('Save failed', 'error')
    }
  }

  return (
    <div className="mb-6 p-4 rounded-xl border border-border-subtle bg-surface">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h3 className="font-semibold text-text-primary">Monitor</h3>
          <Toggle
            enabled={monitorConfig.enable}
            onChange={handleToggleEnable}
          />
          <span className="text-xs text-text-muted">Every {monitorConfig.interval}h</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsConfigOpen(!isConfigOpen)}
            className="px-3 py-1.5 rounded-lg bg-elevated text-sm text-text-secondary hover:text-text-primary transition-colors"
          >
            {isConfigOpen ? 'Hide' : 'Config'}
          </button>
          <button
            onClick={() => handleMonitorAction('test')}
            disabled={isGlobalTesting}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors flex items-center gap-2 ${
              isGlobalTesting
                ? 'bg-elevated text-text-muted cursor-not-allowed'
                : 'border border-accent/30 text-accent hover:bg-accent/10'
            }`}
          >
            {isGlobalTesting && (
              <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            )}
            {isGlobalTesting ? 'Testing...' : 'Test All'}
          </button>
        </div>
      </div>

      {isConfigOpen && (
        <div className="border-t border-border-subtle pt-4 mt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-text-muted mb-1.5">Interval (hours)</label>
              <input
                type="number"
                min="0.1"
                step="0.1"
                max="24"
                value={configForm.interval}
                onChange={(e) =>
                  setConfigForm({ ...configForm, interval: parseFloat(e.target.value) || 6 })
                }
                className="w-full bg-elevated border border-border rounded-lg px-3 py-2 text-text-primary text-sm focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1.5">Telegram Bot Token</label>
              <input
                type="password"
                value={configForm.tg_bot_token || ''}
                onChange={(e) =>
                  setConfigForm({ ...configForm, tg_bot_token: e.target.value || null })
                }
                placeholder="Optional..."
                className="w-full bg-elevated border border-border rounded-lg px-3 py-2 text-text-primary text-sm focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors placeholder-text-muted"
              />
            </div>
            <div>
              <label className="block text-xs text-text-muted mb-1.5">Telegram Chat ID</label>
              <input
                type="text"
                value={configForm.tg_chat_id || ''}
                onChange={(e) =>
                  setConfigForm({ ...configForm, tg_chat_id: e.target.value || null })
                }
                placeholder="Optional..."
                className="w-full bg-elevated border border-border rounded-lg px-3 py-2 text-text-primary text-sm focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors placeholder-text-muted"
              />
            </div>
            <div className="flex items-end">
              <button
                onClick={handleSaveConfig}
                className="px-4 py-2 bg-accent text-white text-sm font-medium rounded-lg hover:bg-accent-hover transition-colors"
              >
                Save Config
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
