<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import http, { errorMessage } from '../api/http'
import { useAuth } from '../stores/auth'
import TablePagination from '../components/TablePagination.vue'
import UserAvatar from '../components/UserAvatar.vue'
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
const loaded = ref(false)
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

const STATUS_TABS = [
  { value: '', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'disabled', label: 'Disabled' },
]

const filtersActive = computed(() => !!(query.search || query.roleId || query.status || query.mfa))
const canUpdate = computed(() => auth.can('users:update'))
const subtitle = computed(() => {
  if (!loaded.value) return 'Loading users…'
  const n = total.value
  if (filtersActive.value) return `${n} ${n === 1 ? 'match' : 'matches'}`
  return `${n} ${n === 1 ? 'user' : 'users'}`
})
const ariaSort = (col) => (query.sort !== col ? 'none' : query.order === 'asc' ? 'ascending' : 'descending')

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
      query.page = lastPage // the page we were on no longer exists
      return load()
    }
    users.value = data.items
    total.value = data.total
    loaded.value = true
    error.value = ''
  } catch (e) {
    if (id === requestId) error.value = errorMessage(e)
  } finally {
    if (id === requestId) loading.value = false
  }
}

// typing waits 300 ms; dropdowns and tabs apply at once; both go back to page 1
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
  query.sort !== column ? 'bi-arrow-down-up' : query.order === 'asc' ? 'bi-arrow-up' : 'bi-arrow-down'

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
  <div class="users-page">
    <header class="page-head">
      <div>
        <h4 class="mb-1">Users</h4>
        <p class="text-body-secondary mb-0" aria-live="polite">{{ subtitle }}</p>
      </div>
      <button v-if="auth.can('users:create')" class="btn btn-primary" @click="showCreate = true">
        <i class="bi bi-person-plus me-1"></i> New user
      </button>
    </header>

    <div v-if="error" class="alert alert-danger alert-dismissible py-2" role="alert">
      {{ error }}
      <button type="button" class="btn-close" aria-label="Dismiss" @click="error = ''"></button>
    </div>

    <section class="panel">
      <div class="toolbar">
        <div class="search">
          <i class="bi bi-search" aria-hidden="true"></i>
          <input v-model="query.search" type="search" class="form-control" placeholder="Search by name or email"
                 aria-label="Search users" />
        </div>

        <div class="seg" role="group" aria-label="Filter by status">
          <button v-for="t in STATUS_TABS" :key="t.value" type="button" :class="['seg-btn', { on: query.status === t.value }]"
                  :aria-pressed="query.status === t.value" @click="query.status = t.value">{{ t.label }}</button>
        </div>

        <select v-if="roles.length" v-model="query.roleId" class="form-select tool-select" aria-label="Filter by role">
          <option value="">All roles</option>
          <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.name }}</option>
        </select>
        <select v-model="query.mfa" class="form-select tool-select" aria-label="Filter by sign-in security">
          <option value="">Any security</option>
          <option value="on">Two-factor on</option>
          <option value="off">Password only</option>
        </select>

        <button v-if="filtersActive" class="btn btn-link text-decoration-none px-1" @click="clearFilters">
          Clear filters
        </button>
      </div>

      <div class="table-wrap" :class="{ refreshing: loading && loaded }">
        <table class="users-table">
          <thead>
            <tr>
              <th :aria-sort="ariaSort('name')">
                <button class="th-btn" @click="sortBy('name')">User <i :class="['bi', sortIcon('name')]"></i></button>
                <button class="th-btn th-sub" :aria-label="'Sort by email'" @click="sortBy('email')">
                  Email <i :class="['bi', sortIcon('email')]"></i>
                </button>
              </th>
              <th :aria-sort="ariaSort('email')" class="col-email">
                <button class="th-btn" @click="sortBy('email')">Email <i :class="['bi', sortIcon('email')]"></i></button>
              </th>
              <th>Roles</th>
              <th>Status</th>
              <th>Sign-in security</th>
              <th v-if="canUpdate" class="text-end"><span class="visually-hidden">Actions</span></th>
            </tr>
          </thead>

          <tbody v-if="!loaded">
            <tr v-for="n in 6" :key="n" class="skeleton-row" aria-hidden="true">
              <td colspan="6">
                <div class="d-flex align-items-center gap-3">
                  <span class="sk sk-avatar"></span>
                  <span class="sk sk-line" style="width: 160px"></span>
                  <span class="sk sk-line ms-auto" style="width: 90px"></span>
                </div>
              </td>
            </tr>
          </tbody>

          <tbody v-else>
            <tr v-for="u in users" :key="u.id" :class="{ inactive: !u.is_active }">
              <td data-label="User">
                <div class="who">
                  <UserAvatar :name="u.full_name" :email="u.email" :dimmed="!u.is_active" />
                  <div class="min-w-0">
                    <div class="who-name">
                      {{ u.full_name || u.email }}
                      <span v-if="u.id === auth.user?.id" class="you">You</span>
                    </div>
                    <div class="who-email">{{ u.email }}</div>
                  </div>
                </div>
              </td>
              <td data-label="Email" class="col-email">{{ u.email }}</td>
              <td data-label="Roles">
                <span v-for="r in u.roles.slice(0, 2)" :key="r.id" class="pill">{{ r.name }}</span>
                <span v-if="u.roles.length > 2" class="pill pill-more"
                      :title="u.roles.slice(2).map((r) => r.name).join(', ')">+{{ u.roles.length - 2 }}</span>
                <span v-if="!u.roles.length" class="text-body-tertiary">No role</span>
              </td>
              <td data-label="Status">
                <span :class="['status', u.is_active ? 'status-on' : 'status-off']">
                  <i class="dot"></i>{{ u.is_active ? 'Active' : 'Disabled' }}
                </span>
              </td>
              <td data-label="Security">
                <div class="sec">
                  <span v-if="u.totp_enabled" class="sec-item sec-ok"><i class="bi bi-shield-check"></i> Authenticator</span>
                  <span v-if="u.passkey_count" class="sec-item sec-ok">
                    <i class="bi bi-key-fill"></i> {{ u.passkey_count }} {{ u.passkey_count === 1 ? 'passkey' : 'passkeys' }}
                  </span>
                  <span v-if="!u.mfa_enabled" class="sec-item sec-none">Password only</span>
                  <span v-if="!u.email_verified" class="sec-item sec-warn">
                    <i class="bi bi-envelope-exclamation"></i> Email not verified
                  </span>
                </div>
              </td>
              <td v-if="canUpdate" class="actions-cell">
                <div class="actions">
                  <button v-if="auth.can('roles:read')" class="icon-btn" title="Edit roles"
                          :aria-label="`Edit roles for ${u.email}`" @click="edit(u)">
                    <i class="bi bi-person-gear"></i>
                  </button>
                  <button v-if="u.id !== auth.user?.id" class="icon-btn" title="Signed-in devices"
                          :aria-label="`Signed-in devices for ${u.email}`" @click="sessionsFor = u">
                    <i class="bi bi-laptop"></i>
                  </button>
                  <span v-else class="icon-slot" aria-hidden="true"></span>
                  <button v-if="u.mfa_enabled" class="icon-btn" title="Reset two-factor"
                          :aria-label="`Reset two-factor for ${u.email}`" @click="reset2fa(u)">
                    <i class="bi bi-shield-x"></i>
                  </button>
                  <span v-else class="icon-slot" aria-hidden="true"></span>
                  <button :class="['icon-btn', u.is_active ? 'icon-danger' : 'icon-success']"
                          :title="u.is_active ? 'Disable user' : 'Enable user'"
                          :aria-label="`${u.is_active ? 'Disable' : 'Enable'} ${u.email}`" @click="toggle(u)">
                    <i :class="['bi', u.is_active ? 'bi-person-slash' : 'bi-person-check']"></i>
                  </button>
                </div>
              </td>
            </tr>

            <tr v-if="!users.length" class="empty-row">
              <td :colspan="canUpdate ? 6 : 5">
                <div class="empty">
                  <i :class="['bi', filtersActive ? 'bi-funnel' : 'bi-people']"></i>
                  <template v-if="filtersActive">
                    <strong>No users match these filters</strong>
                    <span>Try a different search, or clear the filters to see everyone.</span>
                    <button class="btn btn-outline-primary btn-sm" @click="clearFilters">Clear filters</button>
                  </template>
                  <template v-else>
                    <strong>No users yet</strong>
                    <span>People who register, or that you create, will appear here.</span>
                    <button v-if="auth.can('users:create')" class="btn btn-primary btn-sm" @click="showCreate = true">
                      New user
                    </button>
                  </template>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="panel-foot">
        <TablePagination :page="query.page" v-model:page-size="query.pageSize" :total="total" @update:page="setPage" />
      </div>
    </section>

    <UserCreateModal v-if="showCreate" :roles="roles" @close="showCreate = false" @created="onCreated" />
    <UserSessionsModal v-if="sessionsFor" :user="sessionsFor" @close="sessionsFor = null" />

    <div v-if="editing" class="modal d-block" style="background: rgba(0, 0, 0, 0.5)" role="dialog" aria-modal="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Roles for {{ editing.full_name || editing.email }}</h5>
            <button class="btn-close" aria-label="Close" @click="editing = null"></button>
          </div>
          <div class="modal-body">
            <div v-for="r in roles" :key="r.id" class="form-check">
              <input :id="'r' + r.id" v-model="selected" :value="r.id" type="checkbox" class="form-check-input" />
              <label :for="'r' + r.id" class="form-check-label">{{ r.name }}</label>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-light" @click="editing = null">Cancel</button>
            <button class="btn btn-primary" @click="saveRoles">Save roles</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.users-page {
  --radius: 12px;
  --ctl: 8px;
}
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

/* ---- panel ---- */
.panel {
  background: var(--bs-body-bg);
  border: 1px solid var(--bs-border-color);
  border-radius: var(--radius);
  box-shadow: 0 1px 2px rgb(16 24 40 / 0.04);
  overflow: hidden;
}
.panel-foot {
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--bs-border-color);
}

/* ---- toolbar ---- */
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.625rem;
  padding: 0.875rem 1rem;
  border-bottom: 1px solid var(--bs-border-color);
}
.search {
  position: relative;
  flex: 1 1 260px;
  max-width: 380px;
}
.search .bi {
  position: absolute;
  left: 0.8rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--bs-secondary-color);
  pointer-events: none;
}
.search .form-control {
  padding-left: 2.2rem;
  border-radius: var(--ctl);
}
.tool-select {
  width: auto;
  border-radius: var(--ctl);
}
.seg {
  display: inline-flex;
  padding: 3px;
  gap: 2px;
  background: var(--bs-tertiary-bg);
  border-radius: var(--ctl);
}
.seg-btn {
  border: 0;
  background: transparent;
  padding: 0.3rem 0.8rem;
  border-radius: 6px;
  font-size: 0.875rem;
  color: var(--bs-secondary-color);
  transition: background-color 0.15s, color 0.15s;
}
.seg-btn:hover {
  color: var(--bs-body-color);
}
.seg-btn.on {
  background: var(--bs-body-bg);
  color: var(--bs-body-color);
  font-weight: 600;
  box-shadow: 0 1px 2px rgb(16 24 40 / 0.12);
}

/* ---- table ---- */
.table-wrap {
  overflow-x: auto;
  transition: opacity 0.15s;
}
.table-wrap.refreshing {
  opacity: 0.55;
}
.users-table {
  width: 100%;
  border-collapse: collapse;
}
.users-table th {
  padding: 0.65rem 1rem;
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--bs-secondary-color);
  background: var(--bs-tertiary-bg);
  border-bottom: 1px solid var(--bs-border-color);
  white-space: nowrap;
}
.th-btn {
  border: 0;
  background: none;
  padding: 0;
  font: inherit;
  color: inherit;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.th-sub {
  margin-left: 0.9rem;
  font-weight: 500;
}
@media (min-width: 1400px) {
  .th-sub {
    display: none;
  }
}
.th-btn .bi {
  font-size: 0.7rem;
  opacity: 0.5;
}
th[aria-sort='ascending'] .th-btn,
th[aria-sort='descending'] .th-btn {
  color: var(--bs-body-color);
}
th[aria-sort='ascending'] .th-btn .bi,
th[aria-sort='descending'] .th-btn .bi {
  opacity: 1;
  color: var(--bs-primary);
}
.users-table td {
  padding: 0.8rem 1rem;
  vertical-align: middle;
  border-bottom: 1px solid var(--bs-border-color-translucent);
}
.users-table tbody tr:last-child td {
  border-bottom: 0;
}
.users-table tbody tr:not(.skeleton-row):not(.empty-row):hover {
  background: var(--bs-tertiary-bg);
}
.col-email {
  display: none;
  color: var(--bs-secondary-color);
}
@media (min-width: 1400px) {
  .col-email {
    display: table-cell;
  }
  .who-email {
    display: none;
  }
}

/* ---- user cell ---- */
.who {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 220px;
}
.min-w-0 {
  min-width: 0;
}
.who-name {
  font-weight: 600;
  line-height: 1.25;
}
.who-email {
  font-size: 0.8125rem;
  color: var(--bs-secondary-color);
}
.you {
  margin-left: 0.35rem;
  padding: 0.05rem 0.4rem;
  font-size: 0.6875rem;
  font-weight: 600;
  border-radius: 999px;
  color: var(--bs-primary);
  background: var(--bs-primary-bg-subtle);
  vertical-align: 1px;
}
tr.inactive .who-name,
tr.inactive .who-email,
tr.inactive .col-email {
  color: var(--bs-secondary-color);
}

/* ---- roles / status / security ---- */
.pill {
  display: inline-block;
  margin: 0 0.25rem 0.125rem 0;
  padding: 0.15rem 0.6rem;
  font-size: 0.8125rem;
  border-radius: 999px;
  background: var(--bs-secondary-bg);
  color: var(--bs-body-color);
  white-space: nowrap;
}
.pill-more {
  color: var(--bs-secondary-color);
}
.status {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.875rem;
  font-weight: 500;
  white-space: nowrap;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}
.status-on {
  color: var(--bs-success-text-emphasis);
}
.status-on .dot {
  background: var(--bs-success);
  box-shadow: 0 0 0 3px var(--bs-success-bg-subtle);
}
.status-off {
  color: var(--bs-secondary-color);
}
.status-off .dot {
  background: var(--bs-gray-500);
}
.sec {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem 0.75rem;
  font-size: 0.8125rem;
}
.sec-item {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  white-space: nowrap;
}
.sec-ok {
  color: var(--bs-success-text-emphasis);
}
.sec-none {
  color: var(--bs-secondary-color);
}
.sec-warn {
  color: var(--bs-warning-text-emphasis);
}

/* ---- row actions ---- */
.actions-cell {
  width: 1%;
  white-space: nowrap;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.25rem;
}
.icon-btn {
  display: inline-grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: var(--ctl);
  background: transparent;
  color: var(--bs-secondary-color);
  transition: background-color 0.15s, color 0.15s;
}
.icon-slot {
  width: 34px;
  height: 34px;
}
.icon-btn:hover {
  background: var(--bs-secondary-bg);
  color: var(--bs-body-color);
}
.icon-btn.icon-danger:hover {
  background: var(--bs-danger-bg-subtle);
  color: var(--bs-danger-text-emphasis);
}
.icon-btn.icon-success:hover {
  background: var(--bs-success-bg-subtle);
  color: var(--bs-success-text-emphasis);
}
.icon-btn:focus-visible,
.seg-btn:focus-visible,
.th-btn:focus-visible {
  outline: 2px solid var(--bs-primary);
  outline-offset: 2px;
}

/* ---- empty + loading ---- */
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  padding: 3rem 1rem;
  text-align: center;
  color: var(--bs-secondary-color);
}
.empty .bi {
  font-size: 2rem;
  color: var(--bs-secondary-color);
  opacity: 0.7;
}
.empty strong {
  color: var(--bs-body-color);
}
.empty .btn {
  margin-top: 0.5rem;
}
.sk {
  display: block;
  border-radius: 6px;
  background: linear-gradient(90deg, var(--bs-secondary-bg) 25%, var(--bs-tertiary-bg) 50%, var(--bs-secondary-bg) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s linear infinite;
}
.sk-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
}
.sk-line {
  height: 12px;
}
@keyframes shimmer {
  to {
    background-position: -200% 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .sk {
    animation: none;
  }
  .table-wrap,
  .seg-btn,
  .icon-btn {
    transition: none;
  }
}

/* ---- phones: each row becomes a card ---- */
@media (max-width: 767.98px) {
  .page-head {
    align-items: center;
  }
  .search {
    max-width: none;
    flex-basis: 100%;
  }
  .tool-select {
    flex: 1 1 140px;
  }
  .users-table thead {
    display: none;
  }
  .users-table,
  .users-table tbody {
    display: block;
  }
  .users-table tr:not(.skeleton-row):not(.empty-row) {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.5rem 0.75rem;
    padding: 0.9rem 1rem;
    border-bottom: 1px solid var(--bs-border-color);
  }
  .users-table td {
    display: block;
    padding: 0;
    border: 0;
  }
  .users-table td.col-email,
  .icon-slot {
    display: none;
  }
  .users-table tr:not(.skeleton-row):not(.empty-row) {
    grid-template-columns: 1fr auto;
    align-items: center;
  }
  .users-table td[data-label='User'] {
    grid-column: 1;
  }
  .users-table td[data-label='Status'] {
    grid-column: 2;
    grid-row: 1;
  }
  .users-table td[data-label='Roles'],
  .users-table td[data-label='Security'] {
    grid-column: 1 / -1;
  }
  .users-table td.actions-cell {
    grid-column: 1 / -1;
    width: auto;
    padding-top: 0.25rem;
    border-top: 1px solid var(--bs-border-color-translucent);
  }
  .users-table td.actions-cell .actions {
    justify-content: flex-start;
    margin-left: -0.5rem;
  }
  .who {
    min-width: 0;
  }
}
</style>
