<script setup>
import { ref } from 'vue'
import http, { errorMessage } from '../api/http'
import { useAuth } from '../stores/auth'
import TwoFactorCard from '../components/TwoFactorCard.vue'

const auth = useAuth()
const form = ref({ current_password: '', new_password: '', confirm: '' })
const error = ref('')
const success = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  success.value = ''
  if (form.value.new_password !== form.value.confirm) {
    error.value = 'New passwords do not match'
    return
  }
  loading.value = true
  try {
    const { data } = await http.post('/auth/change-password', {
      current_password: form.value.current_password,
      new_password: form.value.new_password,
    })
    success.value = data.message
    form.value = { current_password: '', new_password: '', confirm: '' }
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="max-width: 640px">
    <h4 class="mb-3">My Profile</h4>

    <div class="card border-0 shadow-sm mb-4">
      <div class="card-body">
        <dl class="row mb-0">
          <dt class="col-sm-3">Name</dt>
          <dd class="col-sm-9">{{ auth.user?.full_name }}</dd>
          <dt class="col-sm-3">Email</dt>
          <dd class="col-sm-9">
            {{ auth.user?.email }}
            <span v-if="auth.user?.email_verified" class="badge text-bg-success ms-1">Verified</span>
          </dd>
          <dt class="col-sm-3">Roles</dt>
          <dd class="col-sm-9">
            <span v-for="r in auth.user?.roles" :key="r.id" class="badge text-bg-secondary me-1">{{ r.name }}</span>
          </dd>
          <dt class="col-sm-3">Permissions</dt>
          <dd class="col-sm-9">
            <span v-for="p in auth.user?.permissions" :key="p" class="badge text-bg-light border me-1 mb-1">{{ p }}</span>
            <span v-if="!auth.user?.permissions.length" class="text-muted">None</span>
          </dd>
        </dl>
      </div>
    </div>
    <TwoFactorCard class="mb-4" />
    <div class="card border-0 shadow-sm">
      <div class="card-header bg-white fw-semibold">
        <i class="bi bi-key me-1"></i> Change password
      </div>

      <div class="card-body">
        <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
        <div v-if="success" class="alert alert-success py-2">{{ success }}</div>

        <form @submit.prevent="submit">
          <div class="mb-3">
            <label class="form-label">Current password</label>
            <input v-model="form.current_password" type="password" class="form-control"
                   required autocomplete="current-password" />
          </div>
          <div class="mb-3">
            <label class="form-label">New password</label>
            <input v-model="form.new_password" type="password" class="form-control"
                   required minlength="8" autocomplete="new-password" />
          </div>
          <div class="mb-3">
            <label class="form-label">Confirm new password</label>
            <input v-model="form.confirm" type="password" class="form-control"
                   required autocomplete="new-password" />
          </div>
          <button class="btn btn-primary" :disabled="loading">
            <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>Update password
          </button>
        </form>
      </div>
    </div>
  </div>
</template>