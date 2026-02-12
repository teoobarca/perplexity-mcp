import { useState, useEffect, useCallback, useRef } from 'react'
import { fetchLogs, LogsResponse } from 'lib/api'

export type RefreshInterval = 0 | 5 | 10 | 15

interface UseLogsResult {
  lines: string[]
  filteredLines: string[]
  totalLines: number
  fileSize: number
  isLoading: boolean
  error: string | null
  searchQuery: string
  setSearchQuery: (query: string) => void
  refreshInterval: RefreshInterval
  setRefreshInterval: (interval: RefreshInterval) => void
  isAutoRefresh: boolean
  setIsAutoRefresh: (enabled: boolean) => void
  refresh: () => Promise<void>
  lastUpdate: string | null
}

export function useLogs(adminToken: string): UseLogsResult {
  const [lines, setLines] = useState<string[]>([])
  const [totalLines, setTotalLines] = useState(0)
  const [fileSize, setFileSize] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [refreshInterval, setRefreshInterval] = useState<RefreshInterval>(5)
  const [isAutoRefresh, setIsAutoRefresh] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<string | null>(null)

  const intervalRef = useRef<number | null>(null)

  const refresh = useCallback(async () => {
    if (!adminToken) {
      setError('Not authenticated')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const response: LogsResponse = await fetchLogs(adminToken, 100)

      if (response.status === 'ok') {
        setLines(response.lines || [])
        setTotalLines(response.total_lines || 0)
        setFileSize(response.file_size || 0)
        setLastUpdate(new Date().toLocaleTimeString())
      } else {
        setError(response.message || 'Failed to fetch logs')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch logs')
    } finally {
      setIsLoading(false)
    }
  }, [adminToken])

  // Filter lines based on search query
  const filteredLines = searchQuery
    ? lines.filter((line) => line.toLowerCase().includes(searchQuery.toLowerCase()))
    : lines

  // Auto-refresh effect
  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }

    if (isAutoRefresh && refreshInterval > 0 && adminToken) {
      // Initial fetch
      refresh()

      // Set up interval
      intervalRef.current = window.setInterval(() => {
        refresh()
      }, refreshInterval * 1000)
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [isAutoRefresh, refreshInterval, adminToken, refresh])

  // Fetch on mount if not auto-refreshing
  useEffect(() => {
    if (!isAutoRefresh && adminToken && lines.length === 0) {
      refresh()
    }
  }, [adminToken, isAutoRefresh, lines.length, refresh])

  return {
    lines,
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
  }
}
