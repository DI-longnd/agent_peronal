import type { ServerEvent } from '../types'
import { getToken } from './rest'

/** WebSocket client — auth ngay khi mở, auto-reconnect backoff 1s→2s→4s (max 10s).
 * auth_failed: App gọi close() để dừng hẳn (không reconnect vào token hỏng). */
export class AgentSocket {
  private ws: WebSocket | null = null
  private backoff = 1000
  private closed = false
  private onEvent: (ev: ServerEvent) => void
  private onStatus: (connected: boolean) => void

  constructor(onEvent: (ev: ServerEvent) => void, onStatus: (connected: boolean) => void) {
    this.onEvent = onEvent
    this.onStatus = onStatus
  }

  connect(): void {
    const url =
      (import.meta.env.VITE_WS_URL as string | undefined) ??
      `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`
    const ws = new WebSocket(url)
    this.ws = ws

    ws.onopen = () => {
      this.backoff = 1000
      this.onStatus(true)
      ws.send(JSON.stringify({ type: 'auth', invite_token: getToken() }))
    }
    ws.onmessage = (e) => this.onEvent(JSON.parse(e.data) as ServerEvent)
    ws.onclose = () => {
      this.onStatus(false)
      if (!this.closed) {
        setTimeout(() => this.connect(), this.backoff)
        this.backoff = Math.min(this.backoff * 2, 10000)
      }
    }
  }

  send(obj: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(obj))
  }

  close(): void {
    this.closed = true
    this.ws?.close()
  }
}
