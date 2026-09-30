<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import http, { errorMessage } from '../api/http'

const route = useRoute()
const state = ref('loading') // loading | ok | error
const message = ref('')

onMounted(async () => {
  const token = route.query.token
  if (!token) {
    state.value = 'error'
    message.value = 'This verification link is missing its token.'
    return
  }
  try {
    const { data } = await http.post('/auth/verify-email', { token })
    message.value = data.message
    state.value = 'ok'
  } catch (e) {
    message.value = errorMessage(e)
    state.value = 'error'
  }
})
</script>

<template>
  <div class="auth-wrap p-3">
    <div class="card shadow border-0 w-100 text-center" style="max-width: 420px">
      <div class="card-body p-4">
        <div v-if="state === 'loading'">
          <div class="spinner-border text-primary mb-3"></div>
          <p class="mb-0">Verifying your email...</p>
        </div>

        <div v-else-if="state === 'ok'">
          <i class="bi bi-check-circle text-success fs-1"></i>
          <h4 class="mt-2">Email verified</h4>
          <p class="text-muted">{{ message }}</p>
          <router-link to="/login" class="btn btn-primary">Go to sign in</router-link>
        </div>

        <div v-else>
          <i class="bi bi-x-circle text-danger fs-1"></i>
          <h4 class="mt-2">Verification failed</h4>
          <p class="text-muted">{{ message }}</p>
          <p class="small text-muted">
            Try signing in, and you'll be offered a new verification email.
          </p>
          <router-link to="/login" class="btn btn-primary">Go to sign in</router-link>
        </div>
      </div>
    </div>
  </div>
</template>