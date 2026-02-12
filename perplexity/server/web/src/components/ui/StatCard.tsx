import { ReactNode } from 'react'

interface StatCardProps {
  label: string
  value: string | number
  icon?: ReactNode
  subtitle?: string
  accentColor?: string
}

export function StatCard({ label, value, icon, subtitle, accentColor = 'rgb(var(--accent))' }: StatCardProps) {
  return (
    <div className="group relative rounded-xl border border-border-subtle bg-surface p-5 transition-colors hover:border-border overflow-hidden">
      <div className="absolute top-0 left-0 right-0 h-0.5" style={{ backgroundColor: accentColor }} />
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium text-text-muted mb-2">{label}</div>
          <div className="text-2xl font-semibold text-text-primary truncate">{value}</div>
          {subtitle && (
            <div className="text-xs text-text-muted mt-1">{subtitle}</div>
          )}
        </div>
        {icon && (
          <div
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ml-3"
            style={{ backgroundColor: `${accentColor}15`, color: accentColor }}
          >
            {icon}
          </div>
        )}
      </div>
    </div>
  )
}
