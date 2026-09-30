import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuth } from './auth'

describe('auth store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('is logged out without a stored token', () => {
    expect(useAuth().isLoggedIn).toBe(false)
  })

  it('is logged in when a token is stored', () => {
    localStorage.setItem('token', 'abc')
    setActivePinia(createPinia())
    expect(useAuth().isLoggedIn).toBe(true)
  })

  it('can() reflects the user permissions', () => {
    const auth = useAuth()
    auth.user = { permissions: ['users:read'] }
    expect(auth.can('users:read')).toBe(true)
    expect(auth.can('users:create')).toBe(false)
  })
})