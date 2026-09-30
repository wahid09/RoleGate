<script setup>
import { ref } from 'vue'
import http, { errorMessage } from '../api/http'

defineProps({ roles: { type: Array, default: () => [] } })
const emit = defineEmits(['close', 'created'])

const form = ref({ full_name: '', email: '', password: '', role_ids: [], is_active: true })
const showPw = ref(false)
const error = ref('')
const loading = ref(false)

function generate() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%'
  const bytes = crypto.getRandomValues(new Uint32Array(14))
  form.value.password = Array.from(bytes, (b) => chars[b % chars.length]).join('')
  showPw.value = true
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await http.post('/users', form.value)
    emit('created')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="modal d-block" style="background: rgba(0, 0, 0, 0.5)">
    <div class="modal-dialog modal-dialog-centered">
      <form class="modal-content" @submit.prevent="submit">
        <div class="modal-header">
          <h5 class="modal-title">Create user</h5>
          <button type="button" class="btn-close" @click="emit('close')"></button>
        </div>

        <div class="modal-body">
          <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>

          <div class="mb-3">
            <label class="form-label">Full name</label>
            <input v-model="form.full_name" class="form-control" required minlength="2" />
          </div>
          <div class="mb-3">
            <label class="form-label">Email</label>
            <input v-model="form.email" type="email" class="form-control" required />
          </div>
          <div class="mb-3">
            <label class="form-label">Password</label>
            <div class="input-group">
              <input v-model="form.password" :type="showPw ? 'text' : 'password'"
                     class="form-control" required minlength="8" />
              <button type="button" class="btn btn-outline-secondary" @click="showPw = !showPw">
                <i :class="'bi bi-' + (showPw ? 'eye-slash' : 'eye')"></i>
              </button>
              <button type="button" class="btn btn-outline-secondary" @click="generate">Generate</button>
            </div>
          </div>

          <div v-if="roles.length" class="mb-3">
            <label class="form-label">Roles</label>
            <div v-for="r in roles" :key="r.id" class="form-check">
              <input :id="'nr' + r.id" v-model="form.role_ids" :value="r.id" type="checkbox"
                     class="form-check-input" />
              <label :for="'nr' + r.id" class="form-check-label text-capitalize">{{ r.name }}</label>
            </div>
            <div class="form-text">Leave empty to assign the default "user" role.</div>
          </div>

          <div class="form-check form-switch">
            <input id="active" v-model="form.is_active" type="checkbox" class="form-check-input" />
            <label for="active" class="form-check-label">Account active</label>
          </div>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn btn-light" @click="emit('close')">Cancel</button>
          <button class="btn btn-primary" :disabled="loading">
            <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>Create user
          </button>
        </div>
      </form>
    </div>
  </div>
</template>