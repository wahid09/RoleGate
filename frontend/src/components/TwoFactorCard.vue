<script setup>
import { computed, ref } from 'vue'
import http, { errorMessage } from '../api/http'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const enabled = computed(() => !!auth.user?.totp_enabled)

const setup = ref(null)         // { secret, qr_svg } while enrolling
const code = ref('')
const password = ref('')
const recoveryCodes = ref([])   // shown once, right after turning 2FA on
const showDisable = ref(false)
const error = ref('')
const loading = ref(false)

async function run(fn) {
  error.value = ''
  loading.value = true
  try {
    await fn()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

const start = () =>
  run(async () => {
    const { data } = await http.post('/auth/2fa/setup')
    setup.value = data
    code.value = ''
  })

const confirmEnable = () =>
  run(async () => {
    const { data } = await http.post('/auth/2fa/enable', { code: code.value })
    recoveryCodes.value = data.recovery_codes
    setup.value = null
    code.value = ''
    await auth.fetchMe()
  })

const disable = () =>
  run(async () => {
    await http.post('/auth/2fa/disable', { password: password.value, code: code.value })
    showDisable.value = false
    password.value = ''
    code.value = ''
    await auth.fetchMe()
  })

function download() {
  const blob = new Blob([recoveryCodes.value.join('\n') + '\n'], { type: 'text/plain' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = 'rolegate-recovery-codes.txt'
  a.click()
  URL.revokeObjectURL(a.href)
}

const copy = () => navigator.clipboard?.writeText(recoveryCodes.value.join('\n'))
</script>

<template>
  <div class="card border-0 shadow-sm">
    <div class="card-header bg-white fw-semibold d-flex justify-content-between">
      <span><i class="bi bi-phone me-1"></i> Two-factor authentication</span>
      <span :class="['badge', enabled ? 'text-bg-success' : 'text-bg-secondary']">
        {{ enabled ? 'On' : 'Off' }}
      </span>
    </div>
    <div class="card-body">
      <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>

      <!-- recovery codes, shown once -->
      <div v-if="recoveryCodes.length">
        <div class="alert alert-warning py-2">
          Save these recovery codes now. Each works once, and they will not be shown again.
        </div>
        <div class="row g-2 mb-3">
          <div v-for="c in recoveryCodes" :key="c" class="col-6"><code>{{ c }}</code></div>
        </div>
        <button class="btn btn-outline-secondary btn-sm me-2" @click="download">
          <i class="bi bi-download"></i> Download
        </button>
        <button class="btn btn-outline-secondary btn-sm me-2" @click="copy">
          <i class="bi bi-clipboard"></i> Copy
        </button>
        <button class="btn btn-primary btn-sm" @click="recoveryCodes = []">I have saved them</button>
      </div>

      <!-- turned on -->
      <div v-else-if="enabled">
        <p class="text-muted">Signing in requires a code from your authenticator app.</p>
        <button v-if="!showDisable" class="btn btn-outline-danger btn-sm" @click="showDisable = true">
          Turn off
        </button>
        <form v-else @submit.prevent="disable">
          <div class="mb-2">
            <label class="form-label">Password</label>
            <input v-model="password" type="password" class="form-control" required />
          </div>
          <div class="mb-3">
            <label class="form-label">Authenticator or recovery code</label>
            <input v-model="code" class="form-control" required autocomplete="one-time-code" />
          </div>
          <button class="btn btn-danger btn-sm me-2" :disabled="loading">Turn off</button>
          <button type="button" class="btn btn-light btn-sm" @click="showDisable = false">Cancel</button>
        </form>
      </div>

      <!-- enrolling -->
      <div v-else-if="setup">
        <p>1. Scan this QR code with an authenticator app.</p>
        <img :src="setup.qr_svg" alt="QR code" width="180" height="180" class="mb-2" />
        <p class="small text-muted">
          Can't scan? Enter this key manually: <code>{{ setup.secret }}</code>
        </p>
        <form @submit.prevent="confirmEnable">
          <label class="form-label">2. Enter the 6-digit code it shows</label>
          <div class="input-group" style="max-width: 280px">
            <input v-model="code" class="form-control" inputmode="numeric" maxlength="6"
                   autocomplete="one-time-code" required />
            <button class="btn btn-primary" :disabled="loading">Turn on</button>
          </div>
        </form>
        <button class="btn btn-link btn-sm px-0 mt-2" @click="setup = null">Cancel</button>
      </div>

      <!-- turned off -->
      <div v-else>
        <p class="text-muted">
          Add a second step to sign-in using an authenticator app such as Google Authenticator, Authy or 1Password.
        </p>
        <button class="btn btn-primary btn-sm" :disabled="loading" @click="start">Set up</button>
      </div>
    </div>
  </div>
</template>