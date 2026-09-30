<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'
import { errorMessage } from '../api/http'

const auth = useAuth()
const router = useRouter()
const form = ref({ full_name: '', email: '', password: '', confirm: '' })
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  if (form.value.password !== form.value.confirm) {
    error.value = 'Passwords do not match'
    return
  }
  loading.value = true
  try {
    const { confirm, ...payload } = form.value
    await auth.register(payload)
    router.push({ path: '/login', query: { registered: 1 } })
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-wrap p-3">
    <div class="card shadow border-0 w-100" style="max-width: 460px">
      <div class="card-body p-4">
        <div class="text-center mb-4">
          <i class="bi bi-person-plus text-primary fs-1"></i>
          <h4 class="mt-2">Create account</h4>
        </div>
        <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>

        <form @submit.prevent="submit">
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
            <input v-model="form.password" type="password" class="form-control" required minlength="8" />
          </div>
          <div class="mb-3">
            <label class="form-label">Confirm password</label>
            <input v-model="form.confirm" type="password" class="form-control" required />
          </div>
          <button class="btn btn-primary w-100" :disabled="loading">
            <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>Register
          </button>
        </form>

        <p class="text-center mt-3 mb-0 small">
          Already registered? <router-link to="/login">Sign in</router-link>
        </p>
      </div>
    </div>
  </div>
</template>