<script setup>
import { computed, onMounted, ref } from 'vue'
import http, { errorMessage } from '../api/http'

const pageSize = 20
const items = ref([])
const total = ref(0)
const page = ref(1)
const action = ref('')
const actor = ref('')
const open = ref(null)
const error = ref('')
const loading = ref(false)

const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

async function load() {
  loading.value = true
  try {
    const { data } = await http.get('/audit-logs', {
      params: {
        page: page.value,
        page_size: pageSize,
        action: action.value || undefined,
        actor: actor.value || undefined,
      },
    })
    items.value = data.items
    total.value = data.total
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function go(p) {
  page.value = Math.min(Math.max(1, p), pages.value)
  load()
}

function badge(a) {
  if (a.includes('failed')) return 'text-bg-danger'
  if (a.startsWith('auth.')) return 'text-bg-info'
  if (a.startsWith('role.')) return 'text-bg-warning'
  return 'text-bg-primary'
}

onMounted(load)
</script>

<template>
  <div>
    <h4 class="mb-3">Audit log</h4>
    <div v-if="error" class="alert alert-danger py-2">{{ error }}</div>

    <form class="row g-2 mb-3" @submit.prevent="search">
      <div class="col-12 col-md-3">
        <select v-model="action" class="form-select" @change="search">
          <option value="">All actions</option>
          <option value="auth.">Authentication</option>
          <option value="auth.login_failed">Failed logins</option>
          <option value="user.">User changes</option>
          <option value="role.">Role changes</option>
        </select>
      </div>
      <div class="col-12 col-md-5">
        <input v-model="actor" class="form-control" placeholder="Filter by actor email" />
      </div>
      <div class="col-auto">
        <button class="btn btn-primary"><i class="bi bi-search"></i> Search</button>
      </div>
    </form>

    <div class="card border-0 shadow-sm">
      <div class="table-responsive">
        <table class="table table-hover align-middle mb-0">
          <thead class="table-light">
            <tr><th>When</th><th>Actor</th><th>Action</th><th>Target</th><th>IP</th><th></th></tr>
          </thead>
          <tbody>
            <template v-for="l in items" :key="l.id">
              <tr>
                <td class="text-nowrap">{{ new Date(l.created_at).toLocaleString() }}</td>
                <td>{{ l.actor_email || '-' }}</td>
                <td><span :class="['badge', badge(l.action)]">{{ l.action }}</span></td>
                <td>{{ l.target_type ? `${l.target_type} #${l.target_id}` : '-' }}</td>
                <td>{{ l.ip || '-' }}</td>
                <td class="text-end">
                  <button v-if="l.detail" class="btn btn-sm btn-outline-secondary"
                          @click="open = open === l.id ? null : l.id">
                    <i :class="'bi bi-chevron-' + (open === l.id ? 'up' : 'down')"></i>
                  </button>
                </td>
              </tr>
              <tr v-if="open === l.id">
                <td colspan="6" class="bg-light"><pre class="mb-0 small">{{ JSON.stringify(l.detail, null, 2) }}</pre></td>
              </tr>
            </template>
            <tr v-if="!items.length && !loading">
              <td colspan="6" class="text-center text-muted py-4">No entries</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card-footer bg-white d-flex justify-content-between align-items-center">
        <span class="small text-muted">{{ total }} entries</span>
        <div class="btn-group btn-group-sm">
          <button class="btn btn-outline-secondary" :disabled="page <= 1" @click="go(page - 1)">Prev</button>
          <button class="btn btn-outline-secondary" disabled>{{ page }} / {{ pages }}</button>
          <button class="btn btn-outline-secondary" :disabled="page >= pages" @click="go(page + 1)">Next</button>
        </div>
      </div>
    </div>
  </div>
</template>