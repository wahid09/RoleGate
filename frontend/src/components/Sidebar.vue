<script setup>
import { useAuth } from '../stores/auth'

const auth = useAuth()
const items = [
  { to: '/', icon: 'speedometer2', label: 'Dashboard', perm: 'dashboard:view' },
  { to: '/users', icon: 'people', label: 'Users', perm: 'users:read' },
  { to: '/roles', icon: 'shield-lock', label: 'Roles & Permissions', perm: 'roles:read' },
  { to: '/profile', icon: 'person-circle', label: 'My Profile' },
]
</script>

<template>
  <aside class="app-sidebar d-flex flex-column p-3">
    <div class="fs-5 fw-semibold text-white mb-4">
      <i class="bi bi-shield-check text-primary me-2"></i>RBAC Admin
    </div>
    <ul class="nav nav-pills flex-column gap-1">
      <template v-for="i in items" :key="i.to">
        <li v-if="!i.perm || auth.can(i.perm)" class="nav-item">
          <router-link :to="i.to" class="nav-link">
            <i :class="'bi bi-' + i.icon + ' me-2'"></i>{{ i.label }}
          </router-link>
        </li>
      </template>
    </ul>
    <div class="mt-auto small text-secondary">v1.0</div>
  </aside>
</template>