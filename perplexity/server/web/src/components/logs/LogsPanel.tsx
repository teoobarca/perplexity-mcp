import { useState, useRef, useEffect } from 'react'
import { useLogs, RefreshInterval } from 'hooks/useLogs'
import { Toggle } from '../ui/Toggle'

type LogLevel = 'all' | 'error' | 'warning' | 'info' | 'debug'

const INTERVAL_OPTIONS: { value: RefreshInterval; label: string }[] = [
  { value: 5, label: '5s' },
  { value: 10, label: '10s' },
  { value: 15, label: '15s' },
]

function getLogLevel(line: string): LogLevel {
  if (line.includes(' - ERROR - ') || line.includes(' ERROR ')) return 'error'
  if (line.includes(' - WARNING - ') || line.includes(' WARNING ')) return 'warning'
  if (line.includes(' - DEBUG - ') || line.includes(' DEBUG ')) return 'debug'
  return 'info'
}

function getLineClass(line: string): string {
  const level = getLogLevel(line)
  switch (level) {
    case 'error': return 'text-error'
    case 'warning': return 'text-warning'
    case 'debug': return 'text-text-muted'
    default: return 'text-text-secondary'
  }
}

function highlightMatch(line: string, query: string): JSX.Element {
  if (!query) return <>{line}</>
  const lowerLine = line.toLowerCase()
  const lowerQuery = query.toLowerCase()
  const index = lowerLine.indexOf(lowerQuery)
  if (index === -1) return <>{line}</>
  return (
    <>
      {line.slice(0, index)}
      <span className="bg-warning/30 rounded px-0.5">{line.slice(index, index + query.length)}</span>
      {line.slice(index + query.length)}
    </>
  )
}

export function LogsPanel() {
  const {
    filteredLines,
    totalLines,
    fileSize,
    isLoading,
    error,
    searchQuery,
    setSearchQuery,
    refreshInterval,
    setRefreshInterval,
    isAutoRefresh,
    setIsAutoRefresh,
    refresh,
    lastUpdate,
  } = useLogs()

  const [levelFilter, setLevelFilter] = useState<LogLevel>('all')
  const [followMode, setFollowMode] = useState(true)
  const logRef = useRef<HTMLDivElement>(null)

  const displayLines = levelFilter === 'all'
    ? filteredLines
    : filteredLines.filter((line) => getLogLevel(line) === levelFilter)

  // Auto-scroll when follow mode is enabled
  useEffect(() => {
    if (followMode && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [displayLines, followMode])

  return (
    <div className="space-y-4">
      {/* Controls Bar */}
      <div className="flex flex-col gap-4 rounded-xl border border-border-subtle bg-surface p-4 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted">Auto</span>
            <Toggle enabled={isAutoRefresh} onChange={setIsAutoRefresh} />
          </div>

          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value) as RefreshInterval)}
            disabled={!isAutoRefresh}
            className={`rounded-lg bg-elevated px-2.5 py-1 text-xs border border-border ${
              isAutoRefresh ? 'text-text-secondary' : 'cursor-not-allowed text-text-muted'
            } focus:outline-none focus:ring-1 focus:ring-accent`}
          >
            {INTERVAL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          <select
            value={levelFilter}
            onChange={(e) => setLevelFilter(e.target.value as LogLevel)}
            className="rounded-lg bg-elevated px-2.5 py-1 text-xs border border-border text-text-secondary focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="all">All Levels</option>
            <option value="error">Error</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
            <option value="debug">Debug</option>
          </select>

          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted">Follow</span>
            <Toggle enabled={followMode} onChange={setFollowMode} />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <input
              type="text"
              placeholder="Filter logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-48 rounded-lg border border-border bg-elevated px-3 py-1.5 text-sm text-text-secondary placeholder-text-muted focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-secondary"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>

          <button
            onClick={refresh}
            disabled={isAutoRefresh || isLoading}
            className={`rounded-lg px-4 py-1.5 text-xs transition-colors ${
              isAutoRefresh || isLoading
                ? 'cursor-not-allowed bg-elevated text-text-muted'
                : 'border border-accent/30 text-accent hover:bg-accent/10'
            }`}
          >
            {isLoading ? 'Loading...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Log Content */}
      {error ? (
        <div className="flex h-96 flex-col items-center justify-center rounded-xl border border-error/30 bg-surface">
          <div className="mb-2 text-error">Error</div>
          <div className="text-sm text-text-muted">{error}</div>
          <button
            onClick={refresh}
            className="mt-4 rounded-lg border border-error/30 px-4 py-2 text-sm text-error hover:bg-error/10"
          >
            Retry
          </button>
        </div>
      ) : isLoading && displayLines.length === 0 ? (
        <div className="flex h-96 items-center justify-center rounded-xl border border-border-subtle bg-surface">
          <div className="animate-pulse text-accent">Loading logs...</div>
        </div>
      ) : displayLines.length === 0 ? (
        <div className="flex h-96 items-center justify-center rounded-xl border border-border-subtle bg-surface">
          <div className="text-text-muted">
            {searchQuery || levelFilter !== 'all' ? 'No matching logs' : 'No logs found'}
          </div>
        </div>
      ) : (
        <div
          ref={logRef}
          className="h-96 overflow-y-auto rounded-xl border border-border-subtle bg-surface font-mono text-xs"
        >
          <table className="w-full">
            <tbody>
              {displayLines.map((line, i) => (
                <tr key={i} className="hover:bg-elevated/50">
                  <td className="px-3 py-0.5 text-text-muted select-none text-right w-12 border-r border-border-subtle align-top">{i + 1}</td>
                  <td className={`px-3 py-0.5 whitespace-pre-wrap ${getLineClass(line)}`}>
                    {highlightMatch(line, searchQuery)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Status Bar */}
      <div className="flex justify-between text-xs text-text-muted">
        <span>
          Showing {displayLines.length} / {totalLines} lines
          {(searchQuery || levelFilter !== 'all') && ' (filtered)'}
        </span>
        <span className="flex gap-4">
          <span>File size: {(fileSize / 1024).toFixed(1)} KB</span>
          {lastUpdate && <span>Last update: {lastUpdate}</span>}
        </span>
      </div>
    </div>
  )
}
