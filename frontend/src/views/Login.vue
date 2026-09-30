<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'
import { errorMessage } from '../api/http'

const auth = useAuth()
const router = useRouter()
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(email.value, password.value)
    router.push('/')
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
          <i class="bi bi-shield-check text-primary fs-1"></i>
          <h4 class="mt-2">Sign in</h4>
        </div>
        <div v-if="$route.query.registered" class="alert alert-success py-2">
          Account created. Please sign in.
        </div>
        <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>

        <form @submit.prevent="submit">
          <div class="mb-3">
            <label class="form-label">Email</label>
            <input v-model="email" type="email" class="form-control" required autofocus />
          </div>
          <div class="mb-3">
            <div class="d-flex justify-content-between">
              <label class="form-label">Password</label>
              <router-link to="/forgot-password" class="small">Forgot password?</router-link>
            </div>
            <input v-model="password" type="password" class="form-control" required />
          </div>
          <button class="btn btn-primary w-100" :disabled="loading">
            <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>Sign in
          </button>
        </form>

        <p class="text-center mt-3 mb-0 small">
          No account? <router-link to="/register">Register</router-link>
        </p>

        <div v-if="$route.query.reset" class="alert alert-success py-2">
          Password updated. Please sign in.
        </div>

      </div>
    </div>
  </div>
</template>