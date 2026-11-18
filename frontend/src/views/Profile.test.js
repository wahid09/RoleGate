import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Profile from './Profile.vue'
import { useAuth } from '../stores/auth'

const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('../api/http', () => ({ default: http, errorMessage: (e) => e.message }))
const stub = (name) => ({ template: `<div class="card">${name}</div>` })
const stubs = { TwoFactorCard: stub('2fa'), PasskeysCard: stub('passkeys'), SessionsCard: stub('sessions') }

function setup(user = {}) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuth().user = {
    full_name: 'Ada Lovelace', email: 'ada@example.com', email_verified: true, mfa_enabled: false,
    roles: [{ id: 1, name: 'admin' }], permissions: ['users:read', 'users:create', 'roles:read'], ...user,
  }
  return mount(Profile, { global: { plugins: [pinia], stubs } })
}

describe('Profile', () => {
  beforeEach(() => {
    http.post.mockReset()
    window.location.hash = ''
  })

  it('shows identity, roles and grouped permissions', () => {
    const w = setup()
    expect(w.find('.hero').text()).toContain('Ada Lovelace')
    expect(w.find('.hero').text()).toContain('Verified')
    expect(w.findAll('.perm-row')).toHaveLength(2)
  })

  it('prompts to enable two-step sign-in and jumps to Security', async () => {
    const w = setup()
    expect(w.find('.hero-sec').text()).toContain('off')
    await w.find('.hero-sec button').trigger('click')
    expect(w.find('#panel-security').isVisible()).toBe(true)
    expect(w.find('#panel-account').isVisible()).toBe(false)
  })

  it('switches tabs', async () => {
    const w = setup({ mfa_enabled: true })
    await w.findAll('[role=tab]')[2].trigger('click')
    expect(w.find('#panel-devices').isVisible()).toBe(true)
  })

  it('blocks mismatched passwords', async () => {
    const w = setup()
    await w.find('#pw-current').setValue('old')
    await w.find('#pw-new').setValue('longenough1')
    await w.find('#pw-confirm').setValue('different')
    expect(w.find('.invalid-feedback').exists()).toBe(true)
    expect(w.find('form .btn-primary').attributes('disabled')).toBeDefined()
    expect(http.post).not.toHaveBeenCalled()
  })

  it('changes the password and clears the form', async () => {
    http.post.mockResolvedValue({ data: { message: 'Password updated' } })
    const w = setup()
    await w.find('#pw-current').setValue('old-pass')
    await w.find('#pw-new').setValue('new-pass-123')
    await w.find('#pw-confirm').setValue('new-pass-123')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(http.post).toHaveBeenCalledWith('/auth/change-password', {
      current_password: 'old-pass', new_password: 'new-pass-123',
    })
    expect(w.text()).toContain('Password updated')
    expect(w.find('#pw-new').element.value).toBe('')
  })
})
