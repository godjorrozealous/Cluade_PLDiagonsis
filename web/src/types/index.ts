export interface DiagnosisSummary {
  fault_type: string
  confidence: number
  primary_tool?: string
}

export interface DiagnosisSession {
  session_id: string
  line_name: string
  status: 'pending' | 'diagnosing' | 'modifying' | 'completed' | 'excluded' | 'rechecking'
  created_at: string
  updated_at: string
  latest_summary?: {
    fault_type: string
    confidence: number
    report: string | null
  }
}

export interface SSEEvent {
  event_type: 'start' | 'thinking' | 'result' | 'content' | 'complete' | 'error' | 'status'
  session_id: string
  payload: any
  timestamp: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  eventType?: SSEEvent['event_type']
  timestamp: string
  thinking?: string
  thinkingCollapsed?: boolean
  summary?: DiagnosisSummary
  report?: string
}
