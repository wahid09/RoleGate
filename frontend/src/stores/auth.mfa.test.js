import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../api/http', () => ({ default: { post: vi.fn(), get: vi.fn() } }))

import http from '../api/http'
import { useAuth } from './auth'

describe('two-step login', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('asks for a code instead of signing in when the API requires MFA', async () => {
    http.post.mockResolvedValue({ data: { mfa_required: true, mfa_token: 'temp' } })
    const auth = useAuth()
    const result = await auth.login('a@example.com', 'secret')
    expect(result).toEqual({ mfaRequired: true, mfaToken: 'temp' })
    expect(auth.isLoggedIn).toBe(false)
  })

  it('signs in after a valid code', async () => {
    http.post.mockResolvedValue({ data: { access_token: 'abc' } })
    http.get.mockResolvedValue({ data: { email: 'a@example.com', permissions: [] } })
    const auth = useAuth()
    await auth.loginWithCode('temp', '123456')
    expect(http.post).toHaveBeenCalledWith('/auth/login/2fa', { mfa_token: 'temp', code: '123456' })
    expect(auth.isLoggedIn).toBe(true)
    expect(localStorage.getItem('token')).toBe('abc')
  })
})