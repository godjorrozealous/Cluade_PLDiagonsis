const BASE = ''

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export function getSessions() {
  return request<{ sessions: import('@/types').DiagnosisSession[] }>('/api/sessions')
}

export function switchSession(sessionId: string) {
  return request<{ success: boolean; session: import('@/types').DiagnosisSession }>(
    `/api/sessions/${sessionId}/switch`,
    { method: 'POST' }
  )
}

export function healthCheck() {
  return request<{ status: string }>('/api/health')
}

export interface ToolInfo {
  name: string
  display_name: string
  description: string
  category: string
}

export function getTools() {
  return request<{ tools: ToolInfo[] }>('/api/tools')
}

export interface StrategyInfo {
  name: string
  description: string
  created_at: string
  tool_weights: Record<string, number>
  excluded_tools: string[]
}

export function getStrategies() {
  return request<{ strategies: StrategyInfo[] }>('/api/skills')
}

export function activateStrategy(name: string) {
  return request<{ success: boolean; strategy_name: string; applied_weights: Record<string, number>; applied_exclusions: string[] }>(
    `/api/skills/${encodeURIComponent(name)}/activate`,
    { method: 'POST' }
  )
}

export function deleteStrategy(name: string) {
  return request<{ success: boolean; message: string }>(
    `/api/skills/${encodeURIComponent(name)}`,
    { method: 'DELETE' }
  )
}

export function resetStrategies() {
  return request<{ success: boolean; message: string; default_weights: Record<string, number> }>(
    '/api/skills/reset',
    { method: 'POST' }
  )
}

export function clearSessions() {
  return request<{ success: boolean; message: string }>(
    '/api/sessions/clear',
    { method: 'POST' }
  )
}

export interface SettingsInfo {
  default_weights: Record<string, number>
  weight_range: { min: number; max: number }
  llm: { provider: string; model: string }
}

export function getSettings() {
  return request<SettingsInfo>('/api/settings')
}

export function updateWeights(weights: Record<string, number>) {
  return request<{ success: boolean; message: string; weights: Record<string, number> }>(
    '/api/settings/weights',
    {
      method: 'POST',
      body: JSON.stringify({ weights }),
    }
  )
}
