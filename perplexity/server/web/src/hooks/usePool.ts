import { useState, useEffect, useCallback } from 'react'
import { fetchPoolStatus, fetchMonitorConfig, fetchFallbackConfig, PoolStatus, MonitorConfig, FallbackConfig } from 'lib/api'
import { useAuth } from './useAuth'

export function usePool() {
  const { adminToken } = useAuth()
  const [data, setData] = useState<PoolStatus>({
    total: 0,
    available: 0,
    mode: '-',
    clients: [],
  })
  const [monitorConfig, setMonitorConfig] = useState<MonitorConfig | null>(null)
  const [fallbackConfig, setFallbackConfig] = useState<FallbackConfig>({ fallback_to_auto: true })
  const [isLoading, setIsLoading] = useState(false)
  const [lastSync, setLastSync] = useState<number | null>(null)

  const refreshData = useCallback(async () => {
    if (!adminToken) {
      try {
        const poolData = await fetchPoolStatus()
        setData(poolData)
        setLastSync(Date.now())
      } catch (e) {
        console.error('Failed to fetch pool status:', e)
      }
      return
    }

    setIsLoading(true)
    try {
      const [poolData, monitorResp, fallbackResp] = await Promise.all([
        fetchPoolStatus(),
        fetchMonitorConfig(adminToken),
        fetchFallbackConfig(),
      ])
      setData(poolData)
      setLastSync(Date.now())

      if (monitorResp.status === 'ok' && monitorResp.config) {
        setMonitorConfig(monitorResp.config)
      }
      if (fallbackResp.status === 'ok' && fallbackResp.config) {
        setFallbackConfig(fallbackResp.config)
      }
    } catch (e) {
      console.error('Failed to fetch data:', e)
    } finally {
      setIsLoading(false)
    }
  }, [adminToken])

  useEffect(() => {
    refreshData()
    const interval = setInterval(refreshData, 30000)
    return () => clearInterval(interval)
  }, [refreshData])

  return {
    data,
    monitorConfig,
    setMonitorConfig,
    fallbackConfig,
    setFallbackConfig,
    isLoading,
    lastSync,
    refreshData,
  }
}
