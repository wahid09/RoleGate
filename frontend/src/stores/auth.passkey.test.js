import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../api/http', () => ({ default: { post: vi.fn(), get: vi.fn() } }))
vi.mock('../api/webauthn', () => ({ getCredential: vi.fn(async () => ({ id: 'cred-1' })) }))

import http from '../api/http'
import { getCredential } from '../api/webauthn'
import { useAuth } from './auth'

describe('passkey login', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetches options, asks the browser, then sends the signed assertion', async () => {
    http.post
      .mockResolvedValueOnce({ data: { challenge: 'xyz' } })
      .mockResolvedValueOnce({ data: { access_token: 'tok' } })
    http.get.mockResolvedValue({ data: { email: 'a@example.com', permissions: [] } })

    const auth = useAuth()
    await auth.loginWithPasskey('temp')

    expect(http.post).toHaveBeenNthCalledWith(1, '/auth/login/webauthn/options', { mfa_token: 'temp' })
    expect(getCredential).toHaveBeenCalledWith({ challenge: 'xyz' })
    expect(http.post).toHaveBeenNthCalledWith(2, '/auth/login/webauthn', {
      mfa_token: 'temp', credential: { id: 'cred-1' },
    })
    expect(auth.isLoggedIn).toBe(true)
    expect(localStorage.getItem('token')).toBe('tok')
  })

  it('does not sign in when the browser prompt is cancelled', async () => {
    http.post.mockResolvedValueOnce({ data: { challenge: 'xyz' } })
    getCredential.mockRejectedValueOnce(Object.assign(new Error('x'), { name: 'NotAllowedError' }))
    const auth = useAuth()
    await expect(auth.loginWithPasskey('temp')).rejects.toThrow()
    expect(auth.isLoggedIn).toBe(false)
  })
})
