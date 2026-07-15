// Mirror ĐÚNG event schema PLAN.md 4.1 + protocol 4.2 — đổi schema = sửa PLAN.md trước.

export type ServerEvent =
  | { type: 'auth_ok'; user_name: string }
  | { type: 'auth_failed' }
  | { type: 'device_status'; online: boolean; device_name: string | null }
  | { type: 'session_created'; session_id: string; title: string }
  | { type: 'busy'; session_id: string }
  | { type: 'run_started'; run_id: string; session_id: string }
  | { type: 'tool_call'; agent: string; tool: string; args_preview: string }
  | { type: 'tool_result'; agent: string; tool: string; result_preview: string }
  | { type: 'subagent_started'; name: string; task: string }
  | { type: 'subagent_finished'; name: string; result_preview: string }
  | { type: 'llm_usage'; agent: string; prompt_tokens: number; completion_tokens: number }
  | { type: 'final_answer'; content: string }
  | { type: 'error'; message: string }
  | {
      type: 'run_finished'
      run_id: string
      status: 'ok' | 'error' | 'cancelled' | 'timeout'
      total_prompt_tokens: number
      total_completion_tokens: number
    }

export interface SessionMeta {
  id: string
  title: string
  created_at: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

// --- UI state ---

export interface ToolRow {
  id: number
  agent: string
  tool: string
  argsPreview: string
  resultPreview: string | null
  done: boolean
}

export type ChatItem =
  | { kind: 'user'; content: string }
  | { kind: 'assistant'; content: string }
  | { kind: 'progress'; runId: string | null; rows: ToolRow[]; done: boolean; error: string | null }
