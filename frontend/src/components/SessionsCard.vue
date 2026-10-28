<script setup>
import { onMounted, ref } from 'vue'
import http, { errorMessage } from '../api/http'
import { describeDevice, isMobile } from '../utils/device'

const sessions = ref([])
const error = ref('')
const info = ref('')
const loading = ref(false)

const fmt = (d) => new Date(d).toLocaleString()

async function load() {
  const { data } = await http.get('/auth/sessions')
  sessions.value = data
}

async function run(fn, message) {
  error.value = ''
  info.value = ''
  loading.value = true
  try {
    await fn()
    await load()
    if (message) info.value = message
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

const revoke = (s) => {
  if (!confirm(`Sign out ${describeDevice(s.user_agent)}?`)) return
  return run(() => http.post(`/auth/sessions/${s.id}/revoke`), 'Device signed out.')
}

const revokeOthers = () => {
  if (!confirm('Sign out every other device?')) return
  return run(() => http.post('/auth/sessions/revoke-others'), 'All other devices signed out.')
}

onMounted(() => run(() => Promise.resolve()))
</script>

<template>
  <div class="card border-0 shadow-sm">
    <div class="card-header bg-white fw-semibold d-flex justify-content-between align-items-center">
      <span><i class="bi bi-laptop me-1"></i> Signed-in devices</span>
      <button v-if="sessions.length > 1" class="btn btn-sm btn-outline-danger" :disabled="loading"
              @click="revokeOthers">Sign out all others</button>
    </div>
    <div class="card-body">
      <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
      <div v-if="info" class="alert alert-success py-2">{{ info }}</div>

      <ul class="list-group">
        <li v-for="s in sessions" :key="s.id"
            class="list-group-item d-flex justify-content-between align-items-center">
          <div class="d-flex align-items-center">
            <i :class="['bi fs-4 me-3 text-secondary', isMobile(s.user_agent) ? 'bi-phone' : 'bi-pc-display']"></i>
            <div>
              <div class="fw-semibold">
                {{ describeDevice(s.user_agent) }}
                <span v-if="s.current" class="badge text-bg-success ms-1">This device</span>
              </div>
              <div class="small text-muted">
                {{ s.ip || 'unknown IP' }} · signed in {{ fmt(s.started_at) }} · last active {{ fmt(s.last_active_at) }}
              </div>
            </div>
          </div>
          <button v-if="!s.current" class="btn btn-sm btn-outline-danger" :disabled="loading"
                  @click="revoke(s)">Sign out</button>
        </li>
      </ul>
      <p class="text-muted small mt-3 mb-0">
        A signed-out device can keep using the app for up to 15 minutes, until its current access token expires.
        Changing your password signs out all other devices.
      </p>
    </div>
  </div>
</template>
