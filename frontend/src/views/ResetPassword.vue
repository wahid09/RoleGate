<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http, { errorMessage } from '../api/http'

const route = useRoute()
const router = useRouter()
const token = route.query.token || ''
const password = ref('')
const confirm = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  if (password.value !== confirm.value) {
    error.value = 'Passwords do not match'
    return
  }
  loading.value = true
  try {
    await http.post('/auth/reset-password', { token, new_password: password.value })
    router.push({ path: '/login', query: { reset: 1 } })
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-wrap p-3">
    <div class="card shadow border-0 w-100" style="max-width: 420px">
      <div class="card-body p-4">
        <div class="text-center mb-4">
          <i class="bi bi-shield-lock text-primary fs-1"></i>
          <h4 class="mt-2">Set a new password</h4>
        </div>

        <div v-if="!token" class="alert alert-danger">
          This reset link is missing its token.
          <router-link to="/forgot-password">Request a new one</router-link>
        </div>
        <template v-else>
          <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
          <form @submit.prevent="submit">
            <div class="mb-3">
              <label class="form-label">New password</label>
              <input v-model="password" type="password" class="form-control" required minlength="8" />
            </div>
            <div class="mb-3">
              <label class="form-label">Confirm password</label>
              <input v-model="confirm" type="password" class="form-control" required />
            </div>
            <button class="btn btn-primary w-100" :disabled="loading">
              <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>Update password
            </button>
          </form>
        </template>
      </div>
    </div>
  </div>
</template>