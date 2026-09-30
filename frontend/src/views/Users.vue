<script setup>
import { onMounted, ref } from 'vue'
import http, { errorMessage } from '../api/http'
import { useAuth } from '../stores/auth'
import UserCreateModal from '../components/UserCreateModal.vue'

const auth = useAuth()
const users = ref([])
const roles = ref([])
const editing = ref(null)
const selected = ref([])
const showCreate = ref(false)
const error = ref('')

async function load() {
  users.value = (await http.get('/users')).data
  if (auth.can('roles:read')) roles.value = (await http.get('/roles')).data
}

function edit(u) {
  editing.value = u
  selected.value = u.roles.map((r) => r.id)
}

async function saveRoles() {
  try {
    await http.put(`/users/${editing.value.id}/roles`, { role_ids: selected.value })
    editing.value = null
    await load()
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function toggle(u) {
  try {
    await http.patch(`/users/${u.id}/active`, { is_active: !u.is_active })
    await load()
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function onCreated() {
  showCreate.value = false
  await load()
}

onMounted(load)
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
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead class="table-light">
            <tr>
              <th>Name</th><th>Email</th><th>Roles</th><th>Status</th>
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
              </td>
              <td v-if="auth.can('users:update')" class="text-end">
                <button v-if="auth.can('roles:read')" class="btn btn-sm btn-outline-primary me-1" @click="edit(u)">
                  <i class="bi bi-pencil"></i> Roles
                </button>
                <button class="btn btn-sm btn-outline-secondary" @click="toggle(u)">
                  {{ u.is_active ? 'Disable' : 'Enable' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <UserCreateModal v-if="showCreate" :roles="roles" @close="showCreate = false" @created="onCreated" />

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