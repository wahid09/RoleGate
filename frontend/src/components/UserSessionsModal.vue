<script setup>
import { onMounted, ref } from 'vue'
import http, { errorMessage } from '../api/http'
import { describeDevice } from '../utils/device'

const props = defineProps({ user: { type: Object, required: true } })
const emit = defineEmits(['close'])

const sessions = ref([])
const error = ref('')
const info = ref('')
const loading = ref(false)

const fmt = (d) => new Date(d).toLocaleString()
const base = () => `/users/${props.user.id}/sessions`

async function load() {
  const { data } = await http.get(base())
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
  return run(() => http.post(`${base()}/${s.id}/revoke`), 'Device signed out.')
}

const revokeAll = () => {
  if (!confirm(`Sign ${props.user.email} out of every device now?`)) return
  return run(() => http.post(`${base()}/revoke-all`), 'Signed out everywhere.')
}

onMounted(() => run(() => Promise.resolve()))
</script>

<template>
  <div>
    <div class="modal d-block" tabindex="-1" role="dialog" @click.self="emit('close')">
      <div class="modal-dialog modal-lg modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Sessions · {{ user.email }}</h5>
            <button type="button" class="btn-close" aria-label="Close" @click="emit('close')"></button>
          </div>
          <div class="modal-body">
            <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>
            <div v-if="info" class="alert alert-success py-2">{{ info }}</div>

            <p v-if="!sessions.length && !loading" class="text-muted mb-0">No signed-in devices.</p>
            <ul v-else class="list-group">
              <li v-for="s in sessions" :key="s.id"
                  class="list-group-item d-flex justify-content-between align-items-center">
                <div>
                  <div class="fw-semibold">{{ describeDevice(s.user_agent) }}</div>
                  <div class="small text-muted">
                    {{ s.ip || 'unknown IP' }} · signed in {{ fmt(s.started_at) }} · last active {{ fmt(s.last_active_at) }}
                  </div>
                </div>
                <button class="btn btn-sm btn-outline-danger" :disabled="loading" @click="revoke(s)">Sign out</button>
              </li>
            </ul>
            <p class="text-muted small mt-3 mb-0">
              “Sign out everywhere” also invalidates access tokens that are already issued, so it takes effect
              immediately. Signing out a single device stops it from renewing, but it can keep working until its current
              access token expires (up to 15 minutes).
            </p>
          </div>
          <div class="modal-footer">
            <button class="btn btn-danger" :disabled="loading || !sessions.length" @click="revokeAll">
              <i class="bi bi-box-arrow-right"></i> Sign out everywhere
            </button>
            <button class="btn btn-outline-secondary" @click="emit('close')">Close</button>
          </div>
        </div>
      </div>
    </div>
    <div class="modal-backdrop show"></div>
  </div>
</template>
