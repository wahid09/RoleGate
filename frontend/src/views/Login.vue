<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'
import http, { errorMessage } from '../api/http'
import { passkeysSupported, webauthnErrorMessage } from '../api/webauthn'

const auth = useAuth()
const router = useRouter()
const email = ref('')
const password = ref('')
const code = ref('')
const mfaToken = ref('')
const methods = ref([])
const error = ref('')
const info = ref('')
const unverified = ref(false)
const loading = ref(false)

const needsSecondStep = computed(() => !!mfaToken.value)
const canPasskey = computed(() => methods.value.includes('passkey') && passkeysSupported())
const canCode = computed(() => methods.value.includes('totp') || !canPasskey.value)

function back() {
  mfaToken.value = ''
  methods.value = []
  code.value = ''
  password.value = ''
}

function handleError(e) {
  error.value = webauthnErrorMessage(e) || errorMessage(e)
  unverified.value = e.response?.status === 403 && error.value === 'Email not verified'
  // the 5-minute sign-in session ran out: go back to the password step
  if (needsSecondStep.value && e.response?.status === 400 && /expired/i.test(error.value)) back()
}

async function submit() {
  error.value = ''
  info.value = ''
  unverified.value = false
  loading.value = true
  try {
    if (needsSecondStep.value) {
      await auth.loginWithCode(mfaToken.value, code.value)
      router.push('/')
    } else {
      const result = await auth.login(email.value, password.value)
      if (result.mfaRequired) {
        mfaToken.value = result.mfaToken
        methods.value = result.methods
      } else router.push('/')
    }
  } catch (e) {
    handleError(e)
  } finally {
    loading.value = false
  }
}

async function usePasskey() {
  error.value = ''
  loading.value = true
  try {
    await auth.loginWithPasskey(mfaToken.value)
    router.push('/')
  } catch (e) {
    handleError(e)
  } finally {
    loading.value = false
  }
}

async function resend() {
  try {
    const { data } = await http.post('/auth/resend-verification', { email: email.value })
    info.value = data.message
    error.value = ''
    unverified.value = false
  } catch (e) {
    error.value = errorMessage(e)
  }
}
</script>

<template>
  <div class="auth-wrap p-3">
    <div class="card shadow border-0 w-100" style="max-width: 420px">
      <div class="card-body p-4">
        <div class="text-center mb-4">
          <i :class="['bi text-primary fs-1', needsSecondStep ? 'bi-phone' : 'bi-shield-check']"></i>
          <h4 class="mt-2">{{ needsSecondStep ? 'Verify it’s you' : 'Sign in' }}</h4>
        </div>

        <div v-if="$route.query.registered" class="alert alert-success py-2">
          Account created. Check your inbox to verify your email, then sign in.
        </div>
        <div v-if="$route.query.reset" class="alert alert-success py-2">
          Password updated. Please sign in.
        </div>
        <div v-if="info" class="alert alert-success py-2">{{ info }}</div>
        <div v-if="error" class="alert alert-danger py-2">
          {{ error }}
          <button v-if="unverified" type="button" class="btn btn-link btn-sm p-0 ms-1 align-baseline"
                  @click="resend">Resend verification email</button>
        </div>

        <!-- step 2: passkey and/or code -->
        <template v-if="needsSecondStep">
          <button v-if="canPasskey" type="button" class="btn btn-primary w-100 mb-3" :disabled="loading"
                  @click="usePasskey">
            <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>
            <i v-else class="bi bi-key me-1"></i> Use a passkey
          </button>
          <p v-else-if="methods.includes('passkey') && !methods.includes('totp')" class="text-warning small">
            This browser does not support passkeys. Sign in from a browser that does.
          </p>

          <form v-if="canCode && (methods.includes('totp'))" @submit.prevent="submit">
            <p v-if="canPasskey" class="text-center text-muted small mb-2">or use your authenticator</p>
            <p v-else class="text-muted small">
              Enter the 6-digit code from your authenticator app, or one of your recovery codes.
            </p>
            <div class="mb-3">
              <label class="form-label">Code</label>
              <input v-model="code" class="form-control" inputmode="text" autocomplete="one-time-code"
                     required :autofocus="!canPasskey" />
            </div>
            <button class="btn btn-outline-primary w-100" :disabled="loading">Verify</button>
          </form>
        </template>

        <!-- step 1: password -->
        <form v-else @submit.prevent="submit">
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
            <span v-if="loading" class="spinner-border spinner-border-sm me-2"></span>
            Sign in
          </button>
        </form>

        <p v-if="needsSecondStep" class="text-center mt-3 mb-0 small">
          <a href="#" @click.prevent="back">Back to sign in</a>
        </p>
        <p v-else class="text-center mt-3 mb-0 small">
          No account? <router-link to="/register">Register</router-link>
        </p>
      </div>
    </div>
  </div>
</template>
