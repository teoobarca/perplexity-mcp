const API_BASE = window.location.origin

export interface PoolStatus {
  total: number
  available: number
  mode: string
  clients: ClientInfo[]
}

export interface RateLimitMode {
  available: boolean
  remaining: number | null
  kind: string | null
}

export interface RateLimits {
  pro_remaining?: number | null
  modes?: Record<string, RateLimitMode>
}

export interface ClientInfo {
  id: string
  enabled: boolean
  available: boolean
  state: string
  request_count: number
  fail_count: number
  last_check_at: string | null
  rate_limits?: RateLimits
}

export interface MonitorConfig {
  enable: boolean
  interval: number
  tg_bot_token: string | null
  tg_chat_id: string | null
}

export interface FallbackConfig {
  fallback_to_auto: boolean
}

export interface ApiResponse<T = unknown> {
  status: 'ok' | 'error'
  message?: string
  error?: string
  data?: T
  config?: T
}

export async function fetchPoolStatus(): Promise<PoolStatus> {
  const resp = await fetch(`${API_BASE}/pool/status`)
  return resp.json()
}

export async function fetchMonitorConfig(): Promise<ApiResponse<MonitorConfig>> {
  const resp = await fetch(`${API_BASE}/monitor/config`)
  return resp.json()
}

export async function fetchFallbackConfig(): Promise<ApiResponse<FallbackConfig>> {
  const resp = await fetch(`${API_BASE}/fallback/config`)
  return resp.json()
}

export async function updateFallbackConfig(
  config: Partial<FallbackConfig>
): Promise<ApiResponse<FallbackConfig>> {
  const resp = await fetch(`${API_BASE}/fallback/config`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config),
  })
  return resp.json()
}

export async function apiCall(
  action: string,
  params: Record<string, unknown> = {}
): Promise<ApiResponse> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }

  const url = action.startsWith('monitor')
    ? `${API_BASE}/${action}`
    : `${API_BASE}/pool/${action}`

  const resp = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(params),
  })
  return resp.json()
}

export async function updateMonitorConfig(
  config: Partial<MonitorConfig>
): Promise<ApiResponse<MonitorConfig>> {
  const resp = await fetch(`${API_BASE}/monitor/config`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(config),
  })
  return resp.json()
}

// ============ Logs API ============

export interface LogsResponse {
  status: 'ok' | 'error'
  message?: string
  lines?: string[]
  total_lines?: number
  file_size?: number
}

export async function fetchLogs(
  lines: number = 100
): Promise<LogsResponse> {
  const resp = await fetch(`${API_BASE}/logs/tail?lines=${lines}`)
  return resp.json()
}

// ============ Token Config Export/Import API ============

export interface TokenConfig {
  id: string
  csrf_token: string
  session_token: string
}

export async function downloadSingleTokenConfig(
  clientId: string
): Promise<TokenConfig[]> {
  const resp = await fetch(`${API_BASE}/pool/export/${encodeURIComponent(clientId)}`)
  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ message: resp.statusText }))
    throw new Error(error.message || `Export failed: ${resp.status}`)
  }
  return resp.json()
}

export async function importTokenConfig(
  tokens: TokenConfig[]
): Promise<ApiResponse> {
  const resp = await fetch(`${API_BASE}/pool/import`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(tokens),
  })
  return resp.json()
}
