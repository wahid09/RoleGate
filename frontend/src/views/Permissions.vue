<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import http, { errorMessage } from '../api/http'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const items = ref([])
const loading = ref(true)
const error = ref('')

// filters
const search = ref('')
const kind = ref('all') // all | builtin | custom
const resourceFilter = ref('')
const collapsed = ref(new Set())

// dialogs
const form = ref(null) // null = closed
const formError = ref('')
const saving = ref(false)
const toDelete = ref(null)
const deleting = ref(false)
const codeInput = ref(null)

const MAX_CHIPS = 3
const canEdit = computed(() => auth.can('permissions:update'))
const canDelete = computed(() => auth.can('permissions:delete'))
const showActions = computed(() => canEdit.value || canDelete.value)

const resourceOf = (p) => p.code.split(':')[0]
const actionOf = (p) => p.code.split(':').slice(1).join(':')

const resources = computed(() => [...new Set(items.value.map(resourceOf))].sort())
const counts = computed(() => ({
  all: items.value.length,
  builtin: items.value.filter((p) => p.builtin).length,
  custom: items.value.filter((p) => !p.builtin).length,
}))

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return items.value.filter((p) => {
    if (kind.value === 'builtin' && !p.builtin) return false
    if (kind.value === 'custom' && p.builtin) return false
    if (resourceFilter.value && resourceOf(p) !== resourceFilter.value) return false
    if (!q) return true
    return (
      p.code.includes(q) ||
      (p.description || '').toLowerCase().includes(q) ||
      p.roles.some((r) => r.toLowerCase().includes(q))
    )
  })
})

const groups = computed(() => {
  const map = new Map()
  for (const p of filtered.value) {
    const r = resourceOf(p)
    if (!map.has(r)) map.set(r, [])
    map.get(r).push(p)
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([resource, rows]) => ({
      resource,
      rows: [...rows].sort((a, b) => a.code.localeCompare(b.code)),
    }))
})

const filtersActive = computed(() => !!(search.value.trim() || kind.value !== 'all' || resourceFilter.value))
// While searching, never hide matches inside a collapsed group.
const isOpen = (resource) => !!search.value.trim() || !collapsed.value.has(resource)

function toggle(resource) {
  const next = new Set(collapsed.value)
  if (next.has(resource)) next.delete(resource)
  else next.add(resource)
  collapsed.value = next
}
const allCollapsed = computed(
  () => groups.value.length > 0 && groups.value.every((g) => collapsed.value.has(g.resource)),
)
function toggleAll() {
  collapsed.value = allCollapsed.value ? new Set() : new Set(groups.value.map((g) => g.resource))
}
function clearFilters() {
  search.value = ''
  kind.value = 'all'
  resourceFilter.value = ''
}

async function load() {
  try {
    items.value = (await http.get('/permissions')).data
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

function openNew(resource = '') {
  formError.value = ''
  form.value = { id: null, code: resource ? `${resource}:` : '', description: '', builtin: false }
  nextTick(() => codeInput.value?.focus())
}
function openEdit(p) {
  formError.value = ''
  form.value = { id: p.id, code: p.code, description: p.description, builtin: p.builtin }
  nextTick(() => codeInput.value?.focus())
}
function closeForm() {
  form.value = null
}

async function save() {
  formError.value = ''
  saving.value = true
  const { id, code, description } = form.value
  try {
    if (id) await http.put(`/permissions/${id}`, { code, description })
    else await http.post('/permissions', { code, description })
    form.value = null
    await load()
  } catch (e) {
    formError.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

async function confirmDelete() {
  deleting.value = true
  try {
    await http.delete(`/permissions/${toDelete.value.id}`)
    toDelete.value = null
    await load()
  } catch (e) {
    error.value = errorMessage(e)
    toDelete.value = null
  } finally {
    deleting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="perm-page">
    <header class="page-head">
      <div>
        <div class="small text-muted">Dev Console</div>
        <h4 class="mb-1">Permissions</h4>
        <p class="text-muted small mb-0">
          What each role is allowed to do. Built-in permissions are used by the application and cannot be removed.
        </p>
      </div>
      <button v-if="auth.can('permissions:create')" class="btn btn-primary text-nowrap" @click="openNew()">
        <i class="bi bi-plus-lg me-1"></i>New permission
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
          <input v-model="search" type="search" class="form-control" placeholder="Search code, description or role"
                 aria-label="Search permissions" />
        </div>
        <div class="seg" role="group" aria-label="Filter by type">
          <button v-for="k in [['all', 'All'], ['builtin', 'Built-in'], ['custom', 'Custom']]" :key="k[0]"
                  type="button" class="seg-btn" :class="{ on: kind === k[0] }" :aria-pressed="kind === k[0]"
                  @click="kind = k[0]">
            {{ k[1] }} <span class="seg-count">{{ counts[k[0]] }}</span>
          </button>
        </div>
        <select v-model="resourceFilter" class="form-select tool-select" aria-label="Filter by resource">
          <option value="">All resources</option>
          <option v-for="r in resources" :key="r" :value="r">{{ r }}</option>
        </select>
        <button v-if="groups.length > 1" type="button" class="btn btn-link btn-sm text-decoration-none ms-auto"
                @click="toggleAll">
          <i class="bi me-1" :class="allCollapsed ? 'bi-arrows-expand' : 'bi-arrows-collapse'"></i>
          {{ allCollapsed ? 'Expand all' : 'Collapse all' }}
        </button>
      </div>

      <!-- loading -->
      <div v-if="loading" class="p-3 skeleton" aria-busy="true" aria-label="Loading permissions">
        <div v-for="n in 6" :key="n" class="skel-row">
          <span class="skel" style="width: 180px"></span>
          <span class="skel" style="width: 45%"></span>
          <span class="skel" style="width: 90px"></span>
        </div>
      </div>

      <!-- empty -->
      <div v-else-if="!groups.length" class="empty">
        <i class="bi bi-shield-lock empty-icon" aria-hidden="true"></i>
        <template v-if="filtersActive">
          <div class="fw-semibold">No permissions match your filters</div>
          <div class="text-muted small mb-3">Try a different search or clear the filters.</div>
          <button class="btn btn-outline-secondary btn-sm" @click="clearFilters">Clear filters</button>
        </template>
        <template v-else>
          <div class="fw-semibold">No permissions yet</div>
          <div class="text-muted small mb-3">Create one to start controlling access.</div>
          <button v-if="auth.can('permissions:create')" class="btn btn-primary btn-sm" @click="openNew()">
            New permission
          </button>
        </template>
      </div>

      <!-- groups -->
      <div v-else class="groups">
        <section v-for="g in groups" :key="g.resource" class="group">
          <div class="group-head">
            <button type="button" class="group-toggle" :aria-expanded="isOpen(g.resource)"
                    :aria-controls="`grp-${g.resource}`" @click="toggle(g.resource)">
              <i class="bi bi-chevron-right chev" :class="{ open: isOpen(g.resource) }" aria-hidden="true"></i>
              <span class="group-name">{{ g.resource }}</span>
              <span class="group-count">{{ g.rows.length }}</span>
            </button>
            <button v-if="auth.can('permissions:create')" type="button"
                    class="btn btn-sm btn-link text-decoration-none group-add"
                    :aria-label="`Add a permission to ${g.resource}`" @click="openNew(g.resource)">
              <i class="bi bi-plus"></i> Add
            </button>
          </div>

          <ul v-show="isOpen(g.resource)" :id="`grp-${g.resource}`" class="rows">
            <li v-for="p in g.rows" :key="p.id" class="row-item" :class="{ 'has-actions': showActions }">
              <div class="cell-code">
                <code class="code"><span class="code-res">{{ resourceOf(p) }}:</span><span class="code-act">{{ actionOf(p) }}</span></code>
                <span v-if="p.builtin" class="tag tag-builtin" title="Used by the application code">
                  <i class="bi bi-lock-fill" aria-hidden="true"></i> Built-in
                </span>
              </div>
              <div class="cell-desc" :class="{ muted: !p.description }">
                {{ p.description || 'No description' }}
              </div>
              <div class="cell-roles">
                <template v-if="p.roles.length">
                  <span v-for="r in p.roles.slice(0, MAX_CHIPS)" :key="r" class="pill">{{ r }}</span>
                  <span v-if="p.roles.length > MAX_CHIPS" class="pill pill-more"
                        :title="p.roles.slice(MAX_CHIPS).join(', ')">+{{ p.roles.length - MAX_CHIPS }}</span>
                </template>
                <span v-else class="unused" title="No role has this permission">Not assigned</span>
              </div>
              <div v-if="showActions" class="cell-actions">
                <span class="icon-slot">
                  <button v-if="canEdit" class="icon-btn" :aria-label="`Edit ${p.code}`" title="Edit"
                          @click="openEdit(p)">
                    <i class="bi bi-pencil"></i>
                  </button>
                </span>
                <span class="icon-slot">
                  <button v-if="canDelete && !p.builtin" class="icon-btn danger" :aria-label="`Delete ${p.code}`"
                          title="Delete" @click="toDelete = p">
                    <i class="bi bi-trash"></i>
                  </button>
                </span>
              </div>
            </li>
          </ul>
        </section>
      </div>

      <div v-if="!loading && groups.length" class="panel-foot text-muted small" aria-live="polite">
        Showing {{ filtered.length }} of {{ items.length }} permissions in {{ groups.length }}
        {{ groups.length === 1 ? 'resource' : 'resources' }}
      </div>
    </section>

    <!-- create / edit dialog -->
    <div v-if="form" class="modal d-block" style="background: rgba(0, 0, 0, 0.5)" role="dialog" aria-modal="true"
         aria-labelledby="perm-form-title" @keydown.esc="closeForm" @mousedown.self="closeForm">
      <div class="modal-dialog modal-dialog-centered">
        <form class="modal-content perm-modal" @submit.prevent="save">
          <div class="modal-header">
            <h5 id="perm-form-title" class="modal-title">{{ form.id ? 'Edit permission' : 'New permission' }}</h5>
            <button type="button" class="btn-close" aria-label="Close" @click="closeForm"></button>
          </div>
          <div class="modal-body">
            <div v-if="formError" class="alert alert-danger py-2">{{ formError }}</div>
            <div class="mb-3">
              <label class="form-label" for="perm-code">Code</label>
              <input id="perm-code" ref="codeInput" v-model="form.code" class="form-control font-monospace" required
                     pattern="[a-z][a-z0-9_]*:[a-z][a-z0-9_]*" placeholder="reports:export" autocomplete="off"
                     :disabled="form.builtin" />
              <div class="form-text">
                <template v-if="form.builtin">Built-in codes cannot be renamed.</template>
                <template v-else>Lowercase <code>resource:action</code>, for example <code>reports:export</code>.</template>
              </div>
            </div>
            <div class="mb-1">
              <label class="form-label" for="perm-desc">Description</label>
              <input id="perm-desc" v-model="form.description" class="form-control" maxlength="255"
                     placeholder="What this allows, in plain words" />
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-light" @click="closeForm">Cancel</button>
            <button class="btn btn-primary" :disabled="saving">
              <span v-if="saving" class="spinner-border spinner-border-sm me-2"></span>Save changes
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- delete confirmation -->
    <div v-if="toDelete" class="modal d-block" style="background: rgba(0, 0, 0, 0.5)" role="alertdialog"
         aria-modal="true" aria-labelledby="perm-del-title" @keydown.esc="toDelete = null"
         @mousedown.self="toDelete = null">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content perm-modal">
          <div class="modal-header">
            <h5 id="perm-del-title" class="modal-title">Delete permission</h5>
            <button type="button" class="btn-close" aria-label="Close" @click="toDelete = null"></button>
          </div>
          <div class="modal-body">
            <p class="mb-2">Delete <code>{{ toDelete.code }}</code>? This cannot be undone.</p>
            <div v-if="toDelete.roles.length" class="alert alert-warning py-2 mb-0">
              It will also be removed from:
              <span v-for="r in toDelete.roles" :key="r" class="pill ms-1">{{ r }}</span>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-light" @click="toDelete = null">Cancel</button>
            <button class="btn btn-danger" :disabled="deleting" @click="confirmDelete">
              <span v-if="deleting" class="spinner-border spinner-border-sm me-2"></span>Delete permission
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.perm-page {
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

/* toolbar */
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
.seg-count {
  margin-left: 0.2rem;
  font-size: 0.75rem;
  opacity: 0.7;
}

/* groups */
.group + .group {
  border-top: 1px solid var(--bs-border-color);
}
.group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1rem;
  background: var(--bs-tertiary-bg);
  border-bottom: 1px solid var(--bs-border-color-translucent);
}
.group-toggle {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex: 1;
  padding: 0.6rem 0;
  border: 0;
  background: none;
  text-align: left;
  font-weight: 600;
  color: var(--bs-body-color);
}
.chev {
  font-size: 0.75rem;
  color: var(--bs-secondary-color);
  transition: transform 0.15s;
}
.chev.open {
  transform: rotate(90deg);
}
.group-count {
  padding: 0.05rem 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  border-radius: 999px;
  background: var(--bs-secondary-bg);
  color: var(--bs-secondary-color);
}
.group-add {
  font-size: 0.8125rem;
  padding: 0.15rem 0.4rem;
}

/* rows */
.rows {
  list-style: none;
  margin: 0;
  padding: 0;
}
.row-item {
  display: grid;
  grid-template-columns: minmax(220px, 1.1fr) minmax(0, 1.6fr) minmax(150px, 1fr);
  align-items: center;
  gap: 0.5rem 1rem;
  padding: 0.7rem 1rem;
  border-bottom: 1px solid var(--bs-border-color-translucent);
}
.row-item.has-actions {
  grid-template-columns: minmax(220px, 1.1fr) minmax(0, 1.6fr) minmax(150px, 1fr) auto;
}
.rows .row-item:last-child {
  border-bottom: 0;
}
.row-item:hover {
  background: var(--bs-tertiary-bg);
}
.cell-code {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.code {
  font-size: 0.875rem;
  color: var(--bs-body-color);
  word-break: break-all;
}
.code-res {
  color: var(--bs-secondary-color);
}
.code-act {
  font-weight: 600;
  color: var(--bs-primary);
}
.tag {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.1rem 0.5rem;
  font-size: 0.6875rem;
  font-weight: 600;
  border-radius: 999px;
}
.tag-builtin {
  background: var(--bs-secondary-bg);
  color: var(--bs-secondary-color);
}
.cell-desc {
  font-size: 0.9rem;
  color: var(--bs-body-color);
}
.cell-desc.muted,
.unused {
  color: var(--bs-secondary-color);
  font-style: italic;
  font-size: 0.8125rem;
}
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
.cell-actions {
  display: flex;
  gap: 0.25rem;
  justify-content: flex-end;
}
.icon-slot {
  display: inline-block;
  width: 32px;
  height: 32px;
}
.icon-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--bs-secondary-color);
  transition: background-color 0.15s, color 0.15s;
}
.icon-btn:hover,
.icon-btn:focus-visible {
  background: var(--bs-secondary-bg);
  color: var(--bs-body-color);
}
.icon-btn.danger:hover,
.icon-btn.danger:focus-visible {
  background: var(--bs-danger-bg-subtle);
  color: var(--bs-danger-text-emphasis);
}

/* loading + empty */
.skel-row {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 0.85rem 0;
}
.skel {
  display: block;
  height: 14px;
  border-radius: 6px;
  background: var(--bs-secondary-bg);
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  50% {
    opacity: 0.45;
  }
}
.empty {
  padding: 3rem 1rem;
  text-align: center;
}
.empty-icon {
  display: block;
  font-size: 2rem;
  color: var(--bs-secondary-color);
  margin-bottom: 0.5rem;
}

/* mobile: each row becomes a small card */
@media (max-width: 767.98px) {
  .page-head {
    flex-direction: column;
    align-items: stretch;
  }
  .search {
    max-width: none;
  }
  .row-item,
  .row-item.has-actions {
    grid-template-columns: 1fr auto;
    grid-template-areas:
      'code actions'
      'desc desc'
      'roles roles';
    gap: 0.35rem 0.5rem;
  }
  .cell-code {
    grid-area: code;
  }
  .cell-desc {
    grid-area: desc;
  }
  .cell-roles {
    grid-area: roles;
  }
  .cell-actions {
    grid-area: actions;
  }
  .row-item:not(.has-actions) {
    grid-template-columns: 1fr;
    grid-template-areas: 'code' 'desc' 'roles';
  }
}
@media (prefers-reduced-motion: reduce) {
  .skel,
  .chev {
    animation: none;
    transition: none;
  }
}
</style>
