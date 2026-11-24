export type TokenPair = { access_token: string; refresh_token: string }

let pair: TokenPair | null = null
let pending: Promise<string | null> | null = null
let generation = 0
let anchor: string | null = null

export function setSession(next: TokenPair) {
  generation++
  pair = next
  anchor = next.access_token
  pending = null
}

export function currentAccess(fallback: string | null) {
  return pair && fallback === anchor ? pair.access_token : fallback
}

export function sessionEpoch() { return generation }

export async function renewAccess(stale: string, epoch = generation): Promise<string | null> {
  if (!pair || epoch !== generation) return null
  if (pair.access_token !== stale) return pair.access_token
  if (pending) return pending
  const refresh = pair.refresh_token
  const task = (async () => {
    const response = await fetch('/auth/refresh', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
    if (!response.ok) {
      if (generation === epoch && response.status === 401) pair = null
      return null
    }
    const next = await response.json() as TokenPair
    if (generation !== epoch) {
      void revoke(next.refresh_token)
      return null
    }
    pair = next
    return next.access_token
  })()
  pending = task
  try { return await task } finally { if (pending === task) pending = null }
}

async function revoke(refresh: string) {
  await fetch('/auth/logout', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh }),
  }).catch(() => undefined)
}

export function endSession() {
  const old = pair
  generation++
  pair = null
  anchor = null
  pending = null
  if (old) void revoke(old.refresh_token)
}
