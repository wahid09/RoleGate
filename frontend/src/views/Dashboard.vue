<script setup>
import { onMounted, ref } from 'vue'
import http from '../api/http'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const stats = ref({ users: '—', active: '—', roles: '—' })

onMounted(async () => {
  if (auth.can('users:read')) {
    const { data } = await http.get('/users')
    stats.value.users = data.length
    stats.value.active = data.filter((u) => u.is_active).length
  }
  if (auth.can('roles:read')) {
    const { data } = await http.get('/roles')
    stats.value.roles = data.length
  }
})

const cards = () => [
  { label: 'Total users', value: stats.value.users, icon: 'people', color: 'primary' },
  { label: 'Active users', value: stats.value.active, icon: 'person-check', color: 'success' },
  { label: 'Roles', value: stats.value.roles, icon: 'shield-lock', color: 'warning' },
  { label: 'My permissions', value: auth.user?.permissions.length ?? 0, icon: 'key', color: 'info' },
]
</script>

<template>
  <div>
    <h4 class="mb-1">Welcome back, {{ auth.user?.full_name }}</h4>
    <p class="text-muted">Here is an overview of your workspace.</p>

    <div class="row g-3 mb-4">
      <div v-for="c in cards()" :key="c.label" class="col-12 col-sm-6 col-xl-3">
        <div class="card border-0 shadow-sm h-100">
          <div class="card-body d-flex align-items-center">
            <div :class="`stat-icon bg-${c.color}-subtle text-${c.color} me-3`">
              <i :class="'bi bi-' + c.icon"></i>
            </div>
            <div>
              <div class="fs-4 fw-semibold">{{ c.value }}</div>
              <div class="text-muted small">{{ c.label }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="card border-0 shadow-sm">
      <div class="card-header bg-white fw-semibold">Your permissions</div>
      <div class="card-body">
        <span v-for="p in auth.user?.permissions" :key="p" class="badge text-bg-primary me-2 mb-2">{{ p }}</span>
      </div>
    </div>
  </div>
</template>