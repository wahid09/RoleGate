<script setup>
import { computed, onMounted, ref } from 'vue'
import http, { errorMessage } from '../api/http'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const items = ref([])
const search = ref('')
const form = ref(null)          // null = dialog closed
const error = ref('')
const formError = ref('')
const saving = ref(false)

const groups = computed(() => {
  const q = search.value.trim().toLowerCase()
  const map = new Map()
  for (const p of items.value) {
    if (q && !p.code.includes(q) && !p.description.toLowerCase().includes(q)) continue
    const resource = p.code.split(':')[0]
    if (!map.has(resource)) map.set(resource, [])
    map.get(resource).push(p)
  }
  return [...map.entries()]
})

async function load() {
  try {
    items.value = (await http.get('/permissions')).data
  } catch (e) {
    error.value = errorMessage(e)
  }
}

function openNew() {
  formError.value = ''
  form.value = { id: null, code: '', description: '', builtin: false }
}

function openEdit(p) {
  formError.value = ''
  form.value = { id: p.id, code: p.code, description: p.description, builtin: p.builtin }
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

async function remove(p) {
  const used = p.roles.length ? `\n\nIt will also be removed from: ${p.roles.join(', ')}.` : ''
  if (!confirm(`Delete permission "${p.code}"?${used}`)) return
  try {
    await http.delete(`/permissions/${p.id}`)
    await load()
  } catch (e) {
    error.value = errorMessage(e)
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
      <div>
        <div class="small text-muted">Dev Console</div>
        <h4 class="mb-0">Permissions</h4>
      </div>
      <div class="d-flex gap-2">
        <input v-model="search" class="form-control" style="width: 220px" placeholder="Search..." />
        <button v-if="auth.can('permissions:create')" class="btn btn-primary text-nowrap" @click="openNew">
          <i class="bi bi-plus-lg"></i> New permission
        </button>
      </div>
    </div>

    <div v-if="error" class="alert alert-danger alert-dismissible py-2">
      {{ error }}
      <button type="button" class="btn-close" @click="error = ''"></button>
    </div>

    <div class="card border-0 shadow-sm">
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th>Code</th><th>Description</th><th>Used by roles</th>
              <th v-if="auth.can('permissions:update') || auth.can('permissions:delete')" class="text-end">Actions</th>
            </tr>
          </thead>
          <tbody>
            <template v-for="[resource, rows] in groups" :key="resource">
              <tr class="table-light">
                <td colspan="4" class="fw-semibold text-capitalize small">{{ resource }}</td>
              </tr>
              <tr v-for="p in rows" :key="p.id">
                <td>
                  <code>{{ p.code }}</code>
                  <span v-if="p.builtin" class="badge text-bg-secondary ms-2" title="Used by the application code">
                    <i class="bi bi-lock-fill"></i> Built-in
                  </span>
                </td>
                <td>{{ p.description }}</td>
                <td>
                  <span v-for="r in p.roles" :key="r" class="badge text-bg-light border me-1">{{ r }}</span>
                  <span v-if="!p.roles.length" class="text-muted small">None</span>
                </td>
                <td v-if="auth.can('permissions:update') || auth.can('permissions:delete')" class="text-end text-nowrap">
                  <button v-if="auth.can('permissions:update')" class="btn btn-sm btn-outline-primary me-1"
                          @click="openEdit(p)">
                    <i class="bi bi-pencil"></i>
                  </button>
                  <button v-if="auth.can('permissions:delete') && !p.builtin" class="btn btn-sm btn-outline-danger"
                          @click="remove(p)">
                    <i class="bi bi-trash"></i>
                  </button>
                </td>
              </tr>
            </template>
            <tr v-if="!groups.length">
              <td colspan="4" class="text-center text-muted py-4">No permissions found</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- create / edit dialog -->
    <div v-if="form" class="modal d-block" style="background: rgba(0, 0, 0, 0.5)">
      <div class="modal-dialog modal-dialog-centered">
        <form class="modal-content" @submit.prevent="save">
          <div class="modal-header">
            <h5 class="modal-title">{{ form.id ? 'Edit permission' : 'New permission' }}</h5>
            <button type="button" class="btn-close" @click="form = null"></button>
          </div>
          <div class="modal-body">
            <div v-if="formError" class="alert alert-danger py-2">{{ formError }}</div>
            <div class="mb-3">
              <label class="form-label">Code</label>
              <input v-model="form.code" class="form-control font-monospace" required
                     pattern="[a-z][a-z0-9_]*:[a-z][a-z0-9_]*" placeholder="reports:export"
                     :disabled="form.builtin" />
              <div class="form-text">
                <template v-if="form.builtin">Built-in codes cannot be renamed.</template>
                <template v-else>Lowercase <code>resource:action</code>, for example <code>reports:export</code>.</template>
              </div>
            </div>
            <div class="mb-3">
              <label class="form-label">Description</label>
              <input v-model="form.description" class="form-control" maxlength="255" />
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-light" @click="form = null">Cancel</button>
            <button class="btn btn-primary" :disabled="saving">
              <span v-if="saving" class="spinner-border spinner-border-sm me-2"></span>Save
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>