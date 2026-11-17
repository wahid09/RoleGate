<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import http, { errorMessage } from '../api/http'
import { useAuth } from '../stores/auth'
import TablePagination from '../components/TablePagination.vue'
import UserCreateModal from '../components/UserCreateModal.vue'
import UserSessionsModal from '../components/UserSessionsModal.vue'

const auth = useAuth()

const SIZE_KEY = 'users.pageSize'
const savedSize = (() => {
  try {
    return Number(localStorage.getItem(SIZE_KEY)) || 10
  } catch {
    return 10
  }
})()

const users = ref([])
const total = ref(0)
const roles = ref([])
const loading = ref(false)
const error = ref('')

const query = reactive({
  page: 1,
  pageSize: savedSize,
  search: '',
  roleId: '',
  status: '',
  mfa: '',
  sort: 'id',
  order: 'asc',
})

const editing = ref(null)
const selected = ref([])
const showCreate = ref(false)
const sessionsFor = ref(null)

const filtersActive = computed(() => !!(query.search || query.roleId || query.status || query.mfa))

let requestId = 0 // ignore answers that arrive after a newer request was sent

async function load() {
  const id = ++requestId
  loading.value = true
  try {
    const { data } = await http.get('/users/search', {
      params: {
        page: query.page,
        page_size: query.pageSize,
        search: query.search.trim() || undefined,
        role_id: query.roleId || undefined,
        status: query.status || undefined,
        mfa: query.mfa || undefined,
        sort: query.sort,
        order: query.order,
      },
    })
    if (id !== requestId) return
    const lastPage = Math.max(1, Math.ceil(data.total / query.pageSize))
    if (data.items.length === 0 && query.page > lastPage) {
      query.page = lastPage // e.g. the last row on the last page was just removed from view
      return load()
    }
    users.value = data.items
    total.value = data.total
    error.value = ''
  } catch (e) {
    if (id === requestId) error.value = errorMessage(e)
  } finally {
    if (id === requestId) loading.value = false
  }
}

// typing waits 300 ms; dropdowns apply at once; both go back to page 1
let timer
watch(
  () => query.search,
  () => {
    clearTimeout(timer)
    timer = setTimeout(() => {
      query.page = 1
      load()
    }, 300)
  },
)
watch(
  () => [query.roleId, query.status, query.mfa, query.pageSize],
  () => {
    query.page = 1
    load()
  },
)
watch(
  () => query.pageSize,
  (s) => {
    try {
      localStorage.setItem(SIZE_KEY, String(s))
    } catch {
      /* private mode: just don't remember it */
    }
  },
)
onBeforeUnmount(() => clearTimeout(timer))

function setPage(p) {
  query.page = p
  load()
}

function sortBy(column) {
  if (query.sort === column) query.order = query.order === 'asc' ? 'desc' : 'asc'
  else {
    query.sort = column
    query.order = 'asc'
  }
  query.page = 1
  load()
}

const sortIcon = (column) =>
  query.sort !== column ? 'bi-chevron-expand text-muted' : query.order === 'asc' ? 'bi-caret-up-fill' : 'bi-caret-down-fill'

function clearFilters() {
  clearTimeout(timer)
  Object.assign(query, { search: '', roleId: '', status: '', mfa: '', page: 1 })
  load()
}

function edit(u) {
  editing.value = u
  selected.value = u.roles.map((r) => r.id)
}

async function act(fn) {
  try {
    await fn()
    await load()
  } catch (e) {
    error.value = errorMessage(e)
  }
}

const saveRoles = () =>
  act(async () => {
    await http.put(`/users/${editing.value.id}/roles`, { role_ids: selected.value })
    editing.value = null
  })

const toggle = (u) => act(() => http.patch(`/users/${u.id}/active`, { is_active: !u.is_active }))

const reset2fa = (u) => {
  if (!confirm(`Remove two-factor authentication for ${u.email}?`)) return
  return act(() => http.delete(`/users/${u.id}/2fa`))
}

async function onCreated() {
  showCreate.value = false
  await load()
}

onMounted(async () => {
  if (auth.can('roles:read')) {
    try {
      roles.value = (await http.get('/roles')).data
    } catch (e) {
      error.value = errorMessage(e)
    }
  }
  await load()
})
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h4 class="mb-0">Users</h4>
      <button v-if="auth.can('users:create')" class="btn btn-primary" @click="showCreate = true">
        <i class="bi bi-person-plus"></i> New user
      </button>
    </div>

    <div v-if="error" class="alert alert-danger alert-dismissible py-2">
      {{ error }}
      <button type="button" class="btn-close" @click="error = ''"></button>
    </div>

    <div class="card border-0 shadow-sm">
      <div class="card-body border-bottom">
        <div class="row g-2">
          <div class="col-12 col-lg-4">
            <div class="input-group">
              <span class="input-group-text"><i class="bi bi-search"></i></span>
              <input v-model="query.search" type="search" class="form-control" placeholder="Search name or email" />
            </div>
          </div>
          <div v-if="roles.length" class="col-6 col-lg-2">
            <select v-model="query.roleId" class="form-select" aria-label="Filter by role">
              <option value="">All roles</option>
              <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.name }}</option>
            </select>
          </div>
          <div class="col-6 col-lg-2">
            <select v-model="query.status" class="form-select" aria-label="Filter by status">
              <option value="">Any status</option>
              <option value="active">Active</option>
              <option value="disabled">Disabled</option>
            </select>
          </div>
          <div class="col-6 col-lg-2">
            <select v-model="query.mfa" class="form-select" aria-label="Filter by two-factor">
              <option value="">Any 2FA</option>
              <option value="on">2FA on</option>
              <option value="off">2FA off</option>
            </select>
          </div>
          <div v-if="filtersActive" class="col-6 col-lg-auto">
            <button class="btn btn-outline-secondary w-100" @click="clearFilters">
              <i class="bi bi-x-lg"></i> Clear
            </button>
          </div>
        </div>
      </div>
      <div class="card">
      <div class="card-body">
      <div class="table-responsive" :class="{ 'opacity-50': loading }">
        <table class="table table-hover table-bordered align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th role="button" @click="sortBy('name')">Name <i :class="['bi', sortIcon('name')]"></i></th>
              <th role="button" @click="sortBy('email')">Email <i :class="['bi', sortIcon('email')]"></i></th>
              <th>Roles</th>
              <th>Status</th>
              <th v-if="auth.can('users:update')" class="text-end">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id">
              <td>{{ u.full_name }}</td>
              <td>{{ u.email }}</td>
              <td>
                <span v-for="r in u.roles" :key="r.id" class="badge text-bg-secondary me-1">{{ r.name }}</span>
              </td>
              <td>
                <span :class="['badge', u.is_active ? 'text-bg-success' : 'text-bg-danger']">
                  {{ u.is_active ? 'Active' : 'Disabled' }}
                </span>
                <span v-if="!u.email_verified" class="badge text-bg-warning ms-1">Unverified</span>
                <span v-if="u.mfa_enabled" class="badge text-bg-info ms-1">2FA</span>
              </td>
              <td v-if="auth.can('users:update')" class="text-end text-nowrap">
                <button v-if="auth.can('roles:read')" class="btn btn-sm btn-outline-primary me-1" @click="edit(u)">
                  <i class="bi bi-pencil"></i> Roles
                </button>
                <button v-if="u.id !== auth.user?.id" class="btn btn-sm btn-outline-secondary me-1"
                        @click="sessionsFor = u">Sessions</button>
                <button v-if="u.mfa_enabled" class="btn btn-sm btn-outline-warning me-1" @click="reset2fa(u)">
                  Reset 2FA
                </button>
                <button class="btn btn-sm btn-outline-secondary" @click="toggle(u)">
                  {{ u.is_active ? 'Disable' : 'Enable' }}
                </button>
              </td>
            </tr>
            <tr v-if="!users.length && !loading">
              <td :colspan="auth.can('users:update') ? 5 : 4" class="text-center text-muted py-4">
                {{ filtersActive ? 'No users match these filters.' : 'No users yet.' }}
                <a v-if="filtersActive" href="#" @click.prevent="clearFilters">Clear filters</a>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card-footer bg-white">
        <TablePagination :page="query.page" v-model:page-size="query.pageSize" :total="total"
                         @update:page="setPage" />
      </div>
    </div>
</div>
</div>
    <UserCreateModal v-if="showCreate" :roles="roles" @close="showCreate = false" @created="onCreated" />
    <UserSessionsModal v-if="sessionsFor" :user="sessionsFor" @close="sessionsFor = null" />

    <div v-if="editing" class="modal d-block" style="background: rgba(0, 0, 0, 0.5)">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Roles for {{ editing.full_name }}</h5>
            <button class="btn-close" @click="editing = null"></button>
          </div>
          <div class="modal-body">
            <div v-for="r in roles" :key="r.id" class="form-check">
              <input :id="'r' + r.id" v-model="selected" :value="r.id" type="checkbox" class="form-check-input" />
              <label :for="'r' + r.id" class="form-check-label">{{ r.name }}</label>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-light" @click="editing = null">Cancel</button>
            <button class="btn btn-primary" @click="saveRoles">Save</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
