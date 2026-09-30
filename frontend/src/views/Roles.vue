<script setup>
import { onMounted, ref } from 'vue'
import http, { errorMessage } from '../api/http'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const roles = ref([])
const perms = ref([])
const form = ref(null)
const error = ref('')

async function load() {
  roles.value = (await http.get('/roles')).data
  perms.value = (await http.get('/roles/permissions')).data
}

function openNew() {
  form.value = { id: null, name: '', description: '', permission_ids: [] }
}

function openEdit(r) {
  form.value = {
    id: r.id,
    name: r.name,
    description: r.description,
    permission_ids: r.permissions.map((p) => p.id),
  }
}

async function save() {
  const { id, ...body } = form.value
  try {
    if (id) await http.put(`/roles/${id}`, body)
    else await http.post('/roles', body)
    form.value = null
    await load()
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function remove(r) {
  if (!confirm(`Delete role "${r.name}"?`)) return
  try {
    await http.delete(`/roles/${r.id}`)
    await load()
  } catch (e) {
    error.value = errorMessage(e)
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h4 class="mb-0">Roles &amp; Permissions</h4>
      <button v-if="auth.can('roles:create')" class="btn btn-primary" @click="openNew">
        <i class="bi bi-plus-lg"></i> New role
      </button>
    </div>

    <div v-if="error" class="alert alert-danger alert-dismissible py-2">
      {{ error }}
      <button type="button" class="btn-close" @click="error = ''"></button>
    </div>

    <div class="row g-3">
      <div v-for="r in roles" :key="r.id" class="col-12 col-md-6 col-xl-4">
        <div class="card border-0 shadow-sm h-100">
          <div class="card-body">
            <div class="d-flex justify-content-between">
              <h5 class="text-capitalize">{{ r.name }}</h5>
              <div>
                <button v-if="auth.can('roles:update') && r.name !== 'admin'"
                        class="btn btn-sm btn-outline-primary me-1" @click="openEdit(r)">
                  <i class="bi bi-pencil"></i>
                </button>
                <button v-if="auth.can('roles:delete') && !['admin', 'user'].includes(r.name)"
                        class="btn btn-sm btn-outline-danger" @click="remove(r)">
                  <i class="bi bi-trash"></i>
                </button>
              </div>
            </div>
            <p class="text-muted small">{{ r.description }}</p>
            <span v-for="p in r.permissions" :key="p.id" class="badge text-bg-light border me-1 mb-1">
              {{ p.code }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- create / edit modal -->
    <div v-if="form" class="modal d-block" style="background: rgba(0, 0, 0, 0.5)">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ form.id ? 'Edit role' : 'New role' }}</h5>
            <button class="btn-close" @click="form = null"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label">Name</label>
              <input v-model="form.name" class="form-control" />
            </div>
            <div class="mb-3">
              <label class="form-label">Description</label>
              <input v-model="form.description" class="form-control" />
            </div>
            <label class="form-label">Permissions</label>
            <div v-for="p in perms" :key="p.id" class="form-check">
              <input :id="'p' + p.id" v-model="form.permission_ids" :value="p.id" type="checkbox"
                     class="form-check-input" />
              <label :for="'p' + p.id" class="form-check-label">
                <code>{{ p.code }}</code> <span class="text-muted small">{{ p.description }}</span>
              </label>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-light" @click="form = null">Cancel</button>
            <button class="btn btn-primary" @click="save">Save</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>