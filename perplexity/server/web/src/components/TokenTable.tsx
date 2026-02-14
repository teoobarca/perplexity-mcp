import { useState, useMemo } from 'react'
import { ClientInfo, RateLimits, apiCall, updateFallbackConfig, downloadSingleTokenConfig } from 'lib/api'
import { Toggle } from './ui/Toggle'

type SortField = 'id' | 'state' | 'quota' | 'requests' | 'last_check'
type SortDir = 'asc' | 'desc'
type FilterState = 'all' | 'normal' | 'downgrade' | 'offline' | 'unknown'

interface TokenTableProps {
  clients: ClientInfo[]
  fallbackToAuto: boolean
  onToast: (message: string, type: 'success' | 'error') => void
  onRefresh: () => void
  onAddClick: () => void
  onConfirmDelete: (id: string) => void
  onFallbackChange: (enabled: boolean) => void
}

const STATE_ORDER: Record<string, number> = { normal: 0, unknown: 1, downgrade: 2, offline: 3 }

function getProRemaining(c: ClientInfo): number | null {
  return c.rate_limits?.pro_remaining ?? null
}

function getResearchRemaining(c: ClientInfo): number | null {
  return c.rate_limits?.modes?.['research']?.remaining ?? null
}

function getQuotaSortValue(c: ClientInfo): number {
  const pro = getProRemaining(c)
  if (pro == null) return -1 // unknown at the end
  return pro
}

export function TokenTable({
  clients,
  fallbackToAuto,
  onToast,
  onRefresh,
  onAddClick,
  onConfirmDelete,
  onFallbackChange,
}: TokenTableProps) {
  const [testingIds, setTestingIds] = useState<Set<string>>(new Set())
  const [downloadingIds, setDownloadingIds] = useState<Set<string>>(new Set())
  const [updatingFallback, setUpdatingFallback] = useState(false)
  const [sortField, setSortField] = useState<SortField>('id')
  const [sortDir, setSortDir] = useState<SortDir>('asc')
  const [filter, setFilter] = useState<FilterState>('all')

  const stateCounts = useMemo(() => {
    const counts: Record<string, number> = { all: 0, normal: 0, downgrade: 0, offline: 0, unknown: 0 }
    for (const c of clients || []) {
      counts.all++
      const s = c.state || 'unknown'
      if (s in counts) counts[s]++
      else counts.unknown++
    }
    return counts
  }, [clients])

  const filteredAndSorted = useMemo(() => {
    let list = [...(clients || [])]
    if (filter !== 'all') {
      list = list.filter((c) => (c.state || 'unknown') === filter)
    }
    list.sort((a, b) => {
      let cmp = 0
      switch (sortField) {
        case 'id': cmp = a.id.localeCompare(b.id); break
        case 'state': cmp = (STATE_ORDER[a.state] ?? 9) - (STATE_ORDER[b.state] ?? 9); break
        case 'quota': cmp = getQuotaSortValue(a) - getQuotaSortValue(b); break
        case 'requests': cmp = (a.request_count || 0) - (b.request_count || 0); break
        case 'last_check': cmp = (a.last_check_at || '').localeCompare(b.last_check_at || ''); break
      }
      return sortDir === 'asc' ? cmp : -cmp
    })
    return list
  }, [clients, filter, sortField, sortDir])

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir('asc')
    }
  }

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return null
    return (
      <svg className="w-3 h-3 ml-1 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        {sortDir === 'asc'
          ? <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
          : <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        }
      </svg>
    )
  }

  const maskIdentifier = (id: string) => {
    if (!id || id.length <= 6) return id
    return `${id.substring(0, 3)}***${id.substring(id.length - 3)}`
  }

  const handleClientAction = async (action: string, id: string) => {
    const resp = await apiCall(action, { id })
    if (resp.status === 'ok') { onToast(`Client ${id} ${action}d`, 'success'); onRefresh() }
    else { onToast(resp.message || 'Error', 'error') }
  }

  const handleTestClient = async (id: string) => {
    setTestingIds((prev) => new Set(prev).add(id))
    try {
      const resp = await apiCall('monitor/test', { id })
      if (resp.status === 'ok') { onToast(`Test ${id} passed`, 'success'); onRefresh() }
      else { onToast(resp.error || resp.message || 'Test failed', 'error') }
    } finally {
      setTestingIds((prev) => { const next = new Set(prev); next.delete(id); return next })
    }
  }

  const handleToggleFallback = async () => {
    setUpdatingFallback(true)
    try {
      const newValue = !fallbackToAuto
      const resp = await updateFallbackConfig({ fallback_to_auto: newValue })
      if (resp.status === 'ok') {
        onFallbackChange(newValue)
        onToast(newValue ? 'Fallback enabled' : 'Fallback disabled', 'success')
      } else { onToast(resp.message || 'Error', 'error') }
    } finally { setUpdatingFallback(false) }
  }

  const handleDownload = async (id: string) => {
    setDownloadingIds((prev) => new Set(prev).add(id))
    try {
      const config = await downloadSingleTokenConfig(id)
      const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `token_${id.replace(/[^a-zA-Z0-9]/g, '_')}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      onToast('Config downloaded', 'success')
    } catch (err) {
      onToast(err instanceof Error ? err.message : 'Download failed', 'error')
    } finally {
      setDownloadingIds((prev) => { const next = new Set(prev); next.delete(id); return next })
    }
  }

  const getErrorCount = (c: ClientInfo) => (c.fail_count || 0) + (c.pro_fail_count || 0)

  const filters: { key: FilterState; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'normal', label: 'Pro' },
    { key: 'downgrade', label: 'Downgrade' },
    { key: 'offline', label: 'Offline' },
    { key: 'unknown', label: 'Unknown' },
  ]

  return (
    <div className="rounded-xl border border-border-subtle bg-surface">
      <div className="p-4 md:p-6">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 gap-4 pb-4 border-b border-border-subtle">
          <h2 className="text-lg font-semibold text-text-primary">Active Tokens</h2>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-xs text-text-muted">Fallback</span>
              <Toggle
                enabled={fallbackToAuto}
                onChange={handleToggleFallback}
                disabled={updatingFallback}
              />
            </div>
            <button
              onClick={onAddClick}
              className="px-4 py-2 text-sm font-medium rounded-lg transition-colors bg-accent text-white hover:bg-accent-hover"
            >
              Add Token
            </button>
          </div>
        </div>

        {/* Filter pills */}
        <div className="flex gap-1.5 mb-4 flex-wrap">
          {filters.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                filter === f.key
                  ? 'bg-accent/15 text-accent'
                  : 'bg-elevated text-text-muted hover:text-text-secondary'
              }`}
            >
              {f.label}
              <span className="ml-1.5 opacity-60">{stateCounts[f.key] || 0}</span>
            </button>
          ))}
        </div>

        <div className="overflow-x-auto">
          {filteredAndSorted.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-text-muted">
              <svg className="w-10 h-10 mb-3 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375" />
              </svg>
              <span className="text-sm">{filter !== 'all' ? 'No matching tokens' : 'No tokens configured'}</span>
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-border-subtle">
                  <th className="p-3 text-xs font-medium text-text-muted cursor-pointer select-none" onClick={() => toggleSort('id')}>
                    Identifier<SortIcon field="id" />
                  </th>
                  <th className="p-3 text-xs font-medium text-text-muted cursor-pointer select-none" onClick={() => toggleSort('state')}>
                    State<SortIcon field="state" />
                  </th>
                  <th className="p-3 text-xs font-medium text-text-muted cursor-pointer select-none" onClick={() => toggleSort('quota')}>
                    Quota<SortIcon field="quota" />
                  </th>
                  <th className="p-3 text-xs font-medium text-text-muted cursor-pointer select-none" onClick={() => toggleSort('requests')}>
                    Requests<SortIcon field="requests" />
                  </th>
                  <th className="p-3 text-xs font-medium text-text-muted cursor-pointer select-none" onClick={() => toggleSort('last_check')}>
                    Last Check<SortIcon field="last_check" />
                  </th>
                  <th className="p-3 text-xs font-medium text-text-muted text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {filteredAndSorted.map((c) => {
                  const isDisabledInProOnlyMode = !fallbackToAuto && c.state === 'downgrade'
                  const errors = getErrorCount(c)
                  const pro = getProRemaining(c)
                  const research = getResearchRemaining(c)
                  return (
                    <tr
                      key={c.id}
                      className={`border-b border-border-subtle/50 transition-colors ${
                        isDisabledInProOnlyMode ? 'opacity-40' : 'hover:bg-elevated/50'
                      }`}
                    >
                      <td className="p-3 font-mono text-sm text-text-primary">
                        {maskIdentifier(c.id)}
                      </td>
                      <td className="p-3">
                        {!c.enabled ? (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs bg-elevated text-text-muted">
                            <span className="w-1.5 h-1.5 rounded-full bg-text-muted" />Disabled
                          </span>
                        ) : !c.available ? (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs bg-warning/10 text-warning">
                            <span className="w-1.5 h-1.5 rounded-full bg-warning" />Backoff
                          </span>
                        ) : c.state === 'offline' ? (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs bg-error/10 text-error">
                            <span className="w-1.5 h-1.5 rounded-full bg-error" />Offline
                          </span>
                        ) : c.state === 'downgrade' ? (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs bg-warning/10 text-warning">
                            <span className="w-1.5 h-1.5 rounded-full bg-warning" />Downgrade
                          </span>
                        ) : c.state === 'normal' ? (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs bg-success/10 text-success">
                            <span className="w-1.5 h-1.5 rounded-full bg-success" />Pro
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs bg-info/10 text-info">
                            <span className="w-1.5 h-1.5 rounded-full bg-info" />Ready
                          </span>
                        )}
                      </td>
                      <td className="p-3">
                        <QuotaCell rl={c.rate_limits} />
                      </td>
                      <td className="p-3 text-text-secondary">
                        <div>{c.request_count || 0}</div>
                        {errors > 0 && (
                          <div className="text-error text-xs">{errors} error{errors !== 1 ? 's' : ''}</div>
                        )}
                      </td>
                      <td className="p-3 text-text-muted text-xs font-mono">
                        {c.last_check_at ? new Date(c.last_check_at).toLocaleTimeString() : '-'}
                      </td>
                      <td className="p-3 text-right">
                        <div className="flex justify-end gap-0.5">
                          {/* Download */}
                          <button
                            className={`p-1.5 rounded-md transition-colors ${
                              !downloadingIds.has(c.id) ? 'text-text-muted hover:text-accent hover:bg-elevated' : 'cursor-not-allowed opacity-50'
                            }`}
                            onClick={() => handleDownload(c.id)}
                            title="Download Config"
                            disabled={downloadingIds.has(c.id)}
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                            </svg>
                          </button>
                          {/* Pause/Play */}
                          {c.enabled ? (
                            <button
                              className="p-1.5 rounded-md transition-colors text-text-muted hover:text-warning hover:bg-elevated"
                              onClick={() => handleClientAction('disable', c.id)}
                              title="Disable"
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 5.25v13.5m-7.5-13.5v13.5" />
                              </svg>
                            </button>
                          ) : (
                            <button
                              className="p-1.5 rounded-md transition-colors text-text-muted hover:text-success hover:bg-elevated"
                              onClick={() => handleClientAction('enable', c.id)}
                              title="Enable"
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z" />
                              </svg>
                            </button>
                          )}
                          {/* Test */}
                          <button
                            className={`p-1.5 rounded-md transition-colors ${
                              !testingIds.has(c.id) ? 'text-text-muted hover:text-accent hover:bg-elevated' : 'cursor-not-allowed opacity-50'
                            }`}
                            onClick={() => handleTestClient(c.id)}
                            title="Health Check"
                            disabled={testingIds.has(c.id)}
                          >
                            {testingIds.has(c.id) ? (
                              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                              </svg>
                            ) : (
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                              </svg>
                            )}
                          </button>
                          {/* Delete */}
                          <button
                            className="p-1.5 rounded-md transition-colors text-text-muted hover:text-error hover:bg-elevated"
                            onClick={() => onConfirmDelete(c.id)}
                            title="Remove"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}

function QuotaCell({ rl }: { rl?: RateLimits }) {
  if (!rl) {
    return <span className="text-xs text-text-muted">-</span>
  }

  const pro = rl.pro_remaining
  const modes = rl.modes || {}
  const research = modes['research']
  const agentic = modes['agentic_research']

  const items: { label: string; value: number | null | undefined; color: string }[] = []

  if (pro != null) {
    items.push({
      label: 'Pro',
      value: pro,
      color: pro > 0 ? 'text-success' : 'text-error',
    })
  }

  if (research?.remaining != null) {
    items.push({
      label: 'Research',
      value: research.remaining,
      color: research.remaining > 0 ? 'text-accent' : 'text-error',
    })
  }

  if (agentic?.remaining != null) {
    items.push({
      label: 'Agentic',
      value: agentic.remaining,
      color: agentic.remaining > 0 ? 'text-info' : 'text-error',
    })
  }

  if (items.length === 0) {
    return <span className="text-xs text-text-muted">-</span>
  }

  return (
    <div className="flex flex-col gap-0.5">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5 text-xs">
          <span className="text-text-muted w-14">{item.label}</span>
          <span className={`font-mono font-medium ${item.color}`}>{item.value}</span>
        </div>
      ))}
    </div>
  )
}
