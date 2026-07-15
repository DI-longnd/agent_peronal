import type { ChatMessage, SessionMeta } from '../types'

const TOKEN_KEY = 'invite_token'

/** Đọc ?invite= từ URL (link mời) -> lưu localStorage -> xóa khỏi URL.
 * Khách bấm link là vào được, không gõ gì (PLAN.md quyết định #11). */
export function resolveInviteToken(): string | null {
  const url = new URL(window.location.href)
  const invite = url.searchParams.get('invite')
  if (invite) {
    localStorage.setItem(TOKEN_KEY, invite)
    url.searchParams.delete('invite')
    history.replaceState(null, '', url.toString())
  }
  return localStorage.getItem(TOKEN_KEY)
}

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? ''
}

export function saveToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-Invite-Token': getToken(),
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) throw new Error(`API ${path}: ${res.status}`)
  return res.json() as Promise<T>
}

export const fetchSessions = () => api<SessionMeta[]>('/api/sessions')
export const fetchMessages = (sessionId: string) =>
  api<ChatMessage[]>(`/api/sessions/${sessionId}/messages`)
export const deleteSession = (sessionId: string) =>
  api<{ ok: boolean }>(`/api/sessions/${sessionId}`, { method: 'DELETE' })
export const completePairing = (code: string) =>
  api<{ ok: boolean; device_name: string }>('/api/pair/complete', {
    method: 'POST',
    body: JSON.stringify({ code }),
  })
