import { currentAccess, renewAccess } from './session'

export type DocumentStatus = 'queued' | 'processing' | 'ready' | 'failed'

export type DocumentItem = {
  id: string
  original_name: string
  size_bytes: number
  status: DocumentStatus
  created_at: string
}

export type Citation = {
  number: number
  chunk_id: string
  document_id: string
  filename: string
  page_number: number
  text: string
}

export type StreamEvent =
  | { type: 'token'; payload: { text: string } }
  | { type: 'citations'; payload: { sources: Citation[] } }
  | { type: 'refusal'; payload: { answer: string } }
  | { type: 'error'; payload: { message: string } }
  | { type: 'done'; payload: Record<string, never> }

export async function authorizedFetch(path: string, token: string | null, init: RequestInit = {}): Promise<Response> {
  const send = (key: string | null) => {
    const headers = new Headers(init.headers)
    if (key) headers.set('Authorization', 'Bearer ' + key)
    return fetch(path, { ...init, headers })
  }
  const key = token ? currentAccess(token) : null
  const response = await send(key)
  if (response.status !== 401 || !key || init.signal?.aborted) return response
  const replacement = await renewAccess(key)
  if (!replacement || init.signal?.aborted) return response
  return send(replacement)
}

export async function api<T>(
  path: string,
  token: string | null,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await authorizedFetch(path, token, { ...init, headers })
  if (!response.ok) {
    const info = await response.json().catch(() => ({}))
    throw new Error(typeof info.detail === 'string' ? info.detail : `HTTP ${response.status}`)
  }
  return response.json() as Promise<T>
}

export function parseSse(buffer: string): { events: StreamEvent[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const blocks = normalized.split('\n\n')
  const rest = blocks.pop() ?? ''
  const events: StreamEvent[] = []

  for (const block of blocks) {
    let name = ''
    const parts: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) name = line.slice(6).trim()
      if (line.startsWith('data:')) parts.push(line.slice(5).trimStart())
    }
    if (!['token', 'citations', 'refusal', 'error', 'done'].includes(name)) continue
    try {
      events.push({ type: name, payload: JSON.parse(parts.join('\n')) } as StreamEvent)
    } catch {
      // An incomplete JSON event will be ignored; the stream framing is authoritative.
    }
  }
  return { events, rest }
}

export async function streamAnswer(
  token: string,
  question: string,
  signal: AbortSignal,
  onEvent: (event: StreamEvent) => void,
  conversationId?: string,
): Promise<void> {
  const response = await authorizedFetch('/qa/ask', token, {
    method: 'POST',
    signal,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify({ question, limit: 5, conversation_id: conversationId }),
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}))
    throw new Error(detail.detail || `HTTP ${response.status}`)
  }
  if (!response.body) throw new Error('Streaming is not available in this browser')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let pending = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      pending += decoder.decode(value, { stream: true })
      const parsed = parseSse(pending)
      pending = parsed.rest
      for (const message of parsed.events) onEvent(message)
    }
    pending += decoder.decode()
    const final = parseSse(pending + '\n\n')
    for (const message of final.events) onEvent(message)
  } finally {
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
