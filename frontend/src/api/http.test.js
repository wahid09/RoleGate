import { describe, expect, it } from 'vitest'
import { errorMessage } from './http'

describe('errorMessage', () => {
  it('joins validation errors', () => {
    const e = { response: { data: { detail: [{ msg: 'too short' }, { msg: 'invalid email' }] } } }
    expect(errorMessage(e)).toBe('too short, invalid email')
  })

  it('returns a string detail as-is', () => {
    expect(errorMessage({ response: { data: { detail: 'Email not verified' } } })).toBe('Email not verified')
  })

  it('falls back to a generic message', () => {
    expect(errorMessage(new Error('boom'))).toBe('Something went wrong')
  })
})