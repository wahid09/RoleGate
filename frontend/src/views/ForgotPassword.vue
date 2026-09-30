<script setup>
import { ref } from 'vue'
import http, { errorMessage } from '../api/http'

const email = ref('')
const sent = ref(false)
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await http.post('/auth/forgot-password', { email: email.value })
    sent.value = true
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
          <i class="bi bi-key text-primary fs-1"></i>
          <h4 class="mt-2">Forgot password</h4>
          <p class="text-muted small mb-0">Enter your email and we'll send you a reset link.</p>
        </div>

        <div v-if="sent" class="alert alert-success">
          If that email is registered, a reset link is on its way.
        </div>
        <template v-else>
          <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
          <form @submit.prevent="submit">
            <div class="mb-3">
              <label class="form-label">Email</label>
              <input v-model="email" type="email" class="form-control" required autofocus />
            </div>
            <button class="btn btn-primary w-100" :disabled="loading">
              <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>Send reset link
            </button>
          </form>
        </template>

        <p class="text-center mt-3 mb-0 small"><router-link to="/login">Back to sign in</router-link></p>
      </div>
    </div>
  </div>
</template>