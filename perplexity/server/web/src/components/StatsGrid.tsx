import { useMemo } from 'react'
import { StatCard } from './ui/StatCard'
import { PoolStatus, MonitorConfig } from 'lib/api'

interface StatsGridProps {
  data: PoolStatus
  monitorConfig: MonitorConfig | null
}

export function StatsGrid({ data, monitorConfig }: StatsGridProps) {
  const proCount = useMemo(
    () => (data.clients || []).filter((c) => c.state === 'normal').length,
    [data.clients]
  )

  const downgradeCount = useMemo(
    () => (data.clients || []).filter((c) => c.state === 'downgrade').length,
    [data.clients]
  )

  const availableCount = useMemo(
    () => (data.clients || []).filter((c) => c.enabled && c.state !== 'offline').length,
    [data.clients]
  )

  const getMonitorStatus = () => {
    if (!monitorConfig) return { label: 'Unknown', color: 'rgb(var(--text-muted))' }
    if (!monitorConfig.enable) return { label: 'Disabled', color: 'rgb(var(--text-muted))' }
    return { label: 'Active', color: 'rgb(var(--success))' }
  }

  const monitorStatus = getMonitorStatus()

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      <StatCard
        label="Total Clients"
        value={data.total || 0}
        subtitle={`${availableCount} available`}
        accentColor="rgb(var(--accent))"
        icon={
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
          </svg>
        }
      />
      <StatCard
        label="Pro"
        value={proCount}
        accentColor="rgb(var(--success))"
        icon={
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
          </svg>
        }
      />
      <StatCard
        label="Downgrade"
        value={downgradeCount}
        accentColor="rgb(var(--warning))"
        icon={
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
          </svg>
        }
      />
      <StatCard
        label="Monitor"
        value={monitorStatus.label}
        accentColor={monitorStatus.color}
        icon={
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 9.563C9 9.252 9.252 9 9.563 9h4.874c.311 0 .563.252.563.563v4.874c0 .311-.252.563-.563.563H9.564A.562.562 0 019 14.437V9.564z" />
          </svg>
        }
      />
    </div>
  )
}
