<script setup>
import { computed, onMounted, ref } from 'vue'
import http, { errorMessage } from '../api/http'
import { createCredential, passkeysSupported, webauthnErrorMessage } from '../api/webauthn'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const supported = passkeysSupported()
const passkeys = ref([])
const name = ref('')
const password = ref('')
const removing = ref(null) // passkey being removed
const adding = ref(false)
const error = ref('')
const info = ref('')
const loading = ref(false)

const fmt = (d) => (d ? new Date(d).toLocaleString() : 'never')
const hasPassword = computed(() => password.value.length > 0)

async function load() {
  const { data } = await http.get('/auth/passkeys')
  passkeys.value = data
}

async function run(fn) {
  error.value = ''
  info.value = ''
  loading.value = true
  try {
    await fn()
  } catch (e) {
    error.value = webauthnErrorMessage(e) || errorMessage(e)
  } finally {
    loading.value = false
  }
}

const add = () =>
  run(async () => {
    const { data: options } = await http.post('/auth/passkeys/register/options', { password: password.value })
    const credential = await createCredential(options)
    await http.post('/auth/passkeys/register', { name: name.value || 'Passkey', credential })
    info.value = 'Passkey added.'
    adding.value = false
    name.value = ''
    password.value = ''
    await Promise.all([load(), auth.fetchMe()])
  })

const remove = () =>
  run(async () => {
    await http.post(`/auth/passkeys/${removing.value.id}/remove`, { password: password.value })
    removing.value = null
    password.value = ''
    info.value = 'Passkey removed.'
    await Promise.all([load(), auth.fetchMe()])
  })

function cancel() {
  adding.value = false
  removing.value = null
  password.value = ''
  name.value = ''
  error.value = ''
}

onMounted(() => run(load))
</script>

<template>
  <div class="card border-0 shadow-sm">
    <div class="card-header bg-white fw-semibold d-flex justify-content-between">
      <span><i class="bi bi-key me-1"></i> Passkeys</span>
      <span :class="['badge', passkeys.length ? 'text-bg-success' : 'text-bg-secondary']">
        {{ passkeys.length || 'None' }}
      </span>
    </div>
    <div class="card-body">
      <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
      <div v-if="info" class="alert alert-success py-2">{{ info }}</div>

      <p class="text-muted">
        Use a fingerprint, face unlock, device PIN or security key as your second step when signing in.
      </p>

      <ul v-if="passkeys.length" class="list-group mb-3">
        <li v-for="p in passkeys" :key="p.id"
            class="list-group-item d-flex justify-content-between align-items-center">
          <div>
            <div class="fw-semibold">{{ p.name }}</div>
            <div class="small text-muted">Added {{ fmt(p.created_at) }} · last used {{ fmt(p.last_used_at) }}</div>
          </div>
          <button class="btn btn-sm btn-outline-danger" :disabled="loading"
                  @click="removing = p; adding = false; password = ''">Remove</button>
        </li>
      </ul>

      <form v-if="removing" @submit.prevent="remove">
        <label class="form-label">Confirm your password to remove “{{ removing.name }}”</label>
        <div class="input-group" style="max-width: 360px">
          <input v-model="password" type="password" class="form-control" required autocomplete="current-password" />
          <button class="btn btn-danger" :disabled="loading || !hasPassword">Remove</button>
          <button type="button" class="btn btn-outline-secondary" @click="cancel">Cancel</button>
        </div>
      </form>

      <form v-else-if="adding" @submit.prevent="add">
        <div class="mb-2" style="max-width: 360px">
          <label class="form-label">Name</label>
          <input v-model="name" class="form-control" maxlength="60" placeholder="e.g. Work laptop" />
        </div>
        <div class="mb-3" style="max-width: 360px">
          <label class="form-label">Your password</label>
          <input v-model="password" type="password" class="form-control" required autocomplete="current-password" />
        </div>
        <button class="btn btn-primary btn-sm me-2" :disabled="loading || !hasPassword">Continue</button>
        <button type="button" class="btn btn-outline-secondary btn-sm" @click="cancel">Cancel</button>
      </form>

      <div v-else>
        <button v-if="supported" class="btn btn-primary btn-sm" @click="adding = true; password = ''; info = ''">
          <i class="bi bi-plus-lg"></i> Add a passkey
        </button>
        <p v-else class="text-warning small mb-0">This browser does not support passkeys.</p>
      </div>
    </div>
  </div>
</template>
