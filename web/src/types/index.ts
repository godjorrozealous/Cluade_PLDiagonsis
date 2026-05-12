export interface DiagnosisSession {
  session_id: string
  line_name: string
  status: 'pending' | 'diagnosing' | 'modifying' | 'completed' | 'excluded' | 'rechecking'
  created_at: string
  updated_at: string
}

export interface SSEEvent {
  event_type: 'start' | 'thinking' | 'result' | 'content' | 'complete' | 'error'
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
}
