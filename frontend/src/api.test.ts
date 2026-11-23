import { describe, expect, it } from 'vitest'
import { parseSse } from './api'

describe('parseSse', () => {
  it('parses bilingual tokens and sources with a partial trailing event', () => {
    const chunk = 'event: token\ndata: {"text":"مرحبا"}\n\n'
      + 'event: citations\ndata: {"sources":[{"number":1}]}\n\n'
      + 'event: tok'
    const first = parseSse(chunk)
    expect(first.events).toEqual([
      { type: 'token', payload: { text: 'مرحبا' } },
      { type: 'citations', payload: { sources: [{ number: 1 }] } },
    ])
    expect(first.rest).toBe('event: tok')
    expect(parseSse(first.rest + 'en\ndata: {"text":"!"}\n\n').events).toEqual([
      { type: 'token', payload: { text: '!' } },
    ])
  })

  it('accepts CRLF streams and ignores unknown event names', () => {
    const parsed = parseSse(
      'event: heartbeat\r\ndata: {}\r\n\r\n'
      + 'event: refusal\r\ndata: {"answer":"Not found"}\r\n\r\n',
    )
    expect(parsed.events).toEqual([
      { type: 'refusal', payload: { answer: 'Not found' } },
    ])
  })
})
