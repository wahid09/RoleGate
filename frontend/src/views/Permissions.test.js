import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import Permissions from './Permissions.vue'
import { useAuth } from '../stores/auth'

const ROWS = [
  { id: 1, code: 'users:read', description: 'List users', builtin: true, roles: ['admin', 'user'] },
  { id: 2, code: 'users:create', description: 'Create users', builtin: true, roles: ['admin'] },
  { id: 3, code: 'reports:export', description: 'Export reports', builtin: false, roles: [] },
]
const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() }))
vi.mock('../api/http', () => ({ default: http, errorMessage: (e) => String(e) }))

async function setup(perms = ['permissions:create', 'permissions:update', 'permissions:delete']) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuth().user = { id: 1, permissions: perms }
  const w = mount(Permissions, { global: { plugins: [pinia] } })
  await flushPromises()
  return w
}

describe('Permissions view', () => {
  beforeEach(() => {
    Object.values(http).forEach((f) => f.mockReset())
    http.get.mockResolvedValue({ data: ROWS })
  })

  it('groups by resource', async () => {
    const w = await setup()
    expect(w.findAll('.group-name').map((n) => n.text())).toEqual(['reports', 'users'])
    expect(w.findAll('.row-item')).toHaveLength(3)
  })

  it('filters by type and search', async () => {
    const w = await setup()
    await w.findAll('.seg-btn')[2].trigger('click') // Custom
    expect(w.findAll('.row-item')).toHaveLength(1)
    await w.findAll('.seg-btn')[0].trigger('click')
    await w.find('input[type=search]').setValue('create')
    expect(w.findAll('.row-item')).toHaveLength(1)
    await w.find('input[type=search]').setValue('zzz')
    expect(w.text()).toContain('No permissions match your filters')
  })

  it('never offers delete for built-ins', async () => {
    const w = await setup()
    expect(w.find('[aria-label="Delete users:read"]').exists()).toBe(false)
    expect(w.find('[aria-label="Delete reports:export"]').exists()).toBe(true)
  })

  it('hides actions without permissions', async () => {
    const w = await setup([])
    expect(w.find('.cell-actions').exists()).toBe(false)
  })

  it('confirms before deleting and lists affected roles', async () => {
    http.delete.mockResolvedValue({})
    const w = await setup()
    await w.find('[aria-label="Delete reports:export"]').trigger('click')
    expect(w.find('[role=alertdialog]').exists()).toBe(true)
    await w.find('.btn-danger').trigger('click')
    await flushPromises()
    expect(http.delete).toHaveBeenCalledWith('/permissions/3')
  })

  it('prefills the resource when adding to a group', async () => {
    const w = await setup()
    await w.find('[aria-label="Add a permission to users"]').trigger('click')
    expect(w.find('#perm-code').element.value).toBe('users:')
  })

  it('creates a permission', async () => {
    http.post.mockResolvedValue({})
    const w = await setup()
    await w.find('.page-head .btn-primary').trigger('click')
    await w.find('#perm-code').setValue('reports:view')
    await w.find('#perm-desc').setValue('View')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(http.post).toHaveBeenCalledWith('/permissions', { code: 'reports:view', description: 'View' })
  })
})
