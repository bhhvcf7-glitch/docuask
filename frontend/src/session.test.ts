import { afterEach, expect, test, vi } from 'vitest'
import { endSession, renewAccess, setSession } from './session'

afterEach(() => { endSession(); vi.unstubAllGlobals() })

test('concurrent refreshes share one request and rotate the pair', async () => {
  const fetcher = vi.fn(async () => new Response(JSON.stringify({
    access_token: 'new', refresh_token: 'replacement',
  }), { status: 200 }))
  vi.stubGlobal('fetch', fetcher)
  setSession({ access_token: 'old', refresh_token: 'original' })
  expect(await Promise.all([renewAccess('old'), renewAccess('old')])).toEqual(['new', 'new'])
  expect(fetcher).toHaveBeenCalledTimes(1)
  expect(await renewAccess('old')).toBe('new')
})
