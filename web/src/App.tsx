import { useEffect, useReducer, useRef } from 'react'
import type { ChatItem, ServerEvent, SessionMeta, ToolRow } from './types'
import { AgentSocket } from './api/ws'
import { clearToken, deleteSession, fetchMessages, fetchSessions, resolveInviteToken } from './api/rest'
import InviteGate from './components/InviteGate'
import DeviceBadge from './components/DeviceBadge'
import PairingPanel from './components/PairingPanel'
import Sidebar from './components/Sidebar'
import ChatView from './components/ChatView'
import Composer from './components/Composer'

interface State {
  auth: 'connecting' | 'ok' | 'failed'
  userName: string
  connected: boolean
  device: { online: boolean; name: string | null }
  sessions: SessionMeta[]
  currentSessionId: string | null
  items: ChatItem[]
  running: boolean
  runId: string | null
  runSessionId: string | null // run events chỉ apply khi đang xem đúng session này
  notice: string | null
  showPairing: boolean
}

const initial: State = {
  auth: 'connecting',
  userName: '',
  connected: false,
  device: { online: false, name: null },
  sessions: [],
  currentSessionId: null,
  items: [],
  running: false,
  runId: null,
  runSessionId: null,
  notice: null,
  showPairing: false,
}

type Action =
  | { type: 'ws_event'; ev: ServerEvent }
  | { type: 'ws_status'; connected: boolean }
  | { type: 'sessions_loaded'; sessions: SessionMeta[] }
  | { type: 'select_session'; id: string }
  | { type: 'history_loaded'; sessionId: string; items: ChatItem[] }
  | { type: 'new_chat' }
  | { type: 'sent'; message: string }
  | { type: 'session_deleted'; id: string }
  | { type: 'set_pairing'; show: boolean }
  | { type: 'clear_notice' }

let rowCounter = 0

type ProgressItem = Extract<ChatItem, { kind: 'progress' }>

/** Cập nhật progress item cuối cùng trong items (immutable). */
function patchProgress(
  items: ChatItem[],
  patch: (p: ProgressItem) => Partial<ProgressItem>,
): ChatItem[] {
  const idx = items.findLastIndex((it) => it.kind === 'progress')
  if (idx < 0) return items
  const current = items[idx] as ProgressItem
  const next = [...items]
  next[idx] = { ...current, ...patch(current) }
  return next
}

function reduceWsEvent(state: State, ev: ServerEvent): State {
  switch (ev.type) {
    case 'auth_ok':
      return { ...state, auth: 'ok', userName: ev.user_name }
    case 'auth_failed':
      return { ...state, auth: 'failed' }
    case 'device_status':
      return { ...state, device: { online: ev.online, name: ev.device_name } }
    case 'session_created': {
      const meta: SessionMeta = { id: ev.session_id, title: ev.title, created_at: '' }
      return { ...state, currentSessionId: ev.session_id, sessions: [meta, ...state.sessions] }
    }
    case 'busy':
      // Server không lưu message khi busy — gỡ user item lạc quan vừa thêm
      return {
        ...state,
        items: state.items.slice(0, -1),
        notice: 'Yêu cầu trước vẫn đang chạy — chờ xong rồi gửi lại nhé.',
      }
    case 'run_started': {
      const progress: ProgressItem = { kind: 'progress', runId: ev.run_id, rows: [], done: false, error: null }
      return {
        ...state,
        running: true,
        runId: ev.run_id,
        runSessionId: ev.session_id,
        items: state.currentSessionId === ev.session_id ? [...state.items, progress] : state.items,
      }
    }
    default:
      break
  }

  // Các event còn lại thuộc run đang chạy — chỉ apply khi đang xem đúng session.
  // Progress là ephemeral: chuyển session giữa run thì mất phần đang xem (PLAN.md #16).
  const viewing = state.runSessionId !== null && state.currentSessionId === state.runSessionId

  switch (ev.type) {
    case 'tool_call': {
      if (!viewing) return state
      const row: ToolRow = {
        id: ++rowCounter,
        agent: ev.agent,
        tool: ev.tool,
        argsPreview: ev.args_preview,
        resultPreview: null,
        done: false,
      }
      return { ...state, items: patchProgress(state.items, (p) => ({ rows: [...p.rows, row] })) }
    }
    case 'tool_result': {
      if (!viewing) return state
      return {
        ...state,
        items: patchProgress(state.items, (p) => {
          const rows = [...p.rows]
          const idx = rows.findIndex((r) => !r.done && r.agent === ev.agent && r.tool === ev.tool)
          if (idx >= 0) rows[idx] = { ...rows[idx], done: true, resultPreview: ev.result_preview }
          return { rows }
        }),
      }
    }
    case 'error':
      if (!viewing) return state
      return { ...state, items: patchProgress(state.items, () => ({ error: ev.message })) }
    case 'final_answer': {
      if (!viewing) return state
      const items = patchProgress(state.items, (p) => ({
        done: true,
        rows: p.rows.map((r) => ({ ...r, done: true })),
      }))
      return { ...state, items: [...items, { kind: 'assistant', content: ev.content }] }
    }
    case 'run_finished': {
      const notice =
        ev.status === 'timeout'
          ? 'Yêu cầu chạy quá lâu nên đã tự dừng.'
          : ev.status === 'error'
            ? 'Có lỗi hệ thống trong lúc xử lý.'
            : null
      return { ...state, running: false, runId: null, runSessionId: null, notice }
    }
    default:
      return state // subagent_started/finished, llm_usage: rows đã gom theo field agent
  }
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'ws_event':
      return reduceWsEvent(state, action.ev)
    case 'ws_status':
      return { ...state, connected: action.connected }
    case 'sessions_loaded':
      return { ...state, sessions: action.sessions }
    case 'select_session':
      return { ...state, currentSessionId: action.id, items: [] }
    case 'history_loaded':
      if (state.currentSessionId !== action.sessionId) return state // đã chuyển đi chỗ khác
      return { ...state, items: action.items }
    case 'new_chat':
      return { ...state, currentSessionId: null, items: [] }
    case 'sent':
      return { ...state, items: [...state.items, { kind: 'user', content: action.message }], notice: null }
    case 'session_deleted': {
      const wasCurrent = state.currentSessionId === action.id
      return {
        ...state,
        sessions: state.sessions.filter((s) => s.id !== action.id),
        currentSessionId: wasCurrent ? null : state.currentSessionId,
        items: wasCurrent ? [] : state.items,
      }
    }
    case 'set_pairing':
      return { ...state, showPairing: action.show }
    case 'clear_notice':
      return { ...state, notice: null }
  }
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, initial)
  const socketRef = useRef<AgentSocket | null>(null)
  const token = resolveInviteToken()

  useEffect(() => {
    if (!token) return
    const socket = new AgentSocket(
      (ev) => {
        dispatch({ type: 'ws_event', ev })
        if (ev.type === 'auth_failed') socket.close() // không reconnect vào token hỏng
      },
      (connected) => dispatch({ type: 'ws_status', connected }),
    )
    socketRef.current = socket
    socket.connect()
    fetchSessions().then((sessions) => dispatch({ type: 'sessions_loaded', sessions })).catch(() => {})
    return () => socket.close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Notice tự ẩn sau 5s
  useEffect(() => {
    if (!state.notice) return
    const t = setTimeout(() => dispatch({ type: 'clear_notice' }), 5000)
    return () => clearTimeout(t)
  }, [state.notice])

  if (!token) return <InviteGate failed={false} />
  if (state.auth === 'failed') {
    clearToken()
    return <InviteGate failed={true} />
  }

  const selectSession = (id: string) => {
    dispatch({ type: 'select_session', id })
    fetchMessages(id)
      .then((messages) =>
        dispatch({
          type: 'history_loaded',
          sessionId: id,
          items: messages.map((m) => ({ kind: m.role, content: m.content }) as ChatItem),
        }),
      )
      .catch(() => {})
  }

  const send = (message: string) => {
    dispatch({ type: 'sent', message })
    socketRef.current?.send({ type: 'chat', session_id: state.currentSessionId, message })
  }

  const stop = () => {
    if (state.runId) socketRef.current?.send({ type: 'cancel', run_id: state.runId })
  }

  const removeSession = (id: string) => {
    deleteSession(id)
      .then(() => dispatch({ type: 'session_deleted', id }))
      .catch(() => {})
  }

  return (
    <div className="flex h-screen bg-zinc-100 text-zinc-900">
      <Sidebar
        sessions={state.sessions}
        currentId={state.currentSessionId}
        onSelect={selectSession}
        onNew={() => dispatch({ type: 'new_chat' })}
        onDelete={removeSession}
      />
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-4 py-2.5">
          <h1 className="text-sm font-bold">
            Personal Agent
            {state.userName && <span className="ml-2 font-normal text-zinc-400">· {state.userName}</span>}
          </h1>
          <DeviceBadge
            connected={state.connected}
            device={state.device}
            onPairClick={() => dispatch({ type: 'set_pairing', show: true })}
          />
        </header>

        {!state.device.online && (
          <div className="border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-center text-xs text-amber-700">
            Máy của bạn chưa kết nối — mở app <b>Personal Agent</b> trên máy tính để agent thao tác web được.{' '}
            <button className="underline" onClick={() => dispatch({ type: 'set_pairing', show: true })}>
              Hướng dẫn ghép máy
            </button>
          </div>
        )}

        <ChatView items={state.items} />

        {state.notice && (
          <div className="mx-auto mb-2 rounded-lg bg-zinc-800 px-4 py-2 text-xs text-white shadow">
            {state.notice}
          </div>
        )}

        <Composer running={state.running} onSend={send} onStop={stop} />
      </main>

      {state.showPairing && <PairingPanel onClose={() => dispatch({ type: 'set_pairing', show: false })} />}
    </div>
  )
}
