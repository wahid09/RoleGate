<script setup>
import { computed, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const route = useRoute()

const menu = [
  { to: '/', icon: 'speedometer2', label: 'Dashboard', perm: 'dashboard:view' },
  {
    key: 'dev',
    icon: 'terminal',
    label: 'Dev Console',
    children: [
      { to: '/dev/users', icon: 'people', label: 'Users', perm: 'users:read' },
      { to: '/dev/roles', icon: 'shield-lock', label: 'Roles', perm: 'roles:read' },
      { to: '/dev/permissions', icon: 'key', label: 'Permissions', perm: 'permissions:read' },
      { to: '/dev/audit', icon: 'clipboard-data', label: 'Audit Log', perm: 'audit:read' },
    ],
  },
  { to: '/profile', icon: 'person-circle', label: 'My Profile' },
]

const visible = computed(() =>
  menu
    .map((item) =>
      item.children
        ? { ...item, children: item.children.filter((c) => !c.perm || auth.can(c.perm)) }
        : item,
    )
    .filter((item) => (item.children ? item.children.length > 0 : !item.perm || auth.can(item.perm))),
)

const open = reactive({ dev: route.path.startsWith('/dev') })
watch(
  () => route.path,
  (path) => {
    if (path.startsWith('/dev')) open.dev = true
  },
)
</script>

<template>
  <aside class="app-sidebar d-flex flex-column p-3">
    <div class="fs-5 fw-semibold text-white mb-4">
      <i class="bi bi-shield-check text-primary me-2"></i>RBAC Admin
    </div>

    <ul class="nav nav-pills flex-column gap-1">
      <li v-for="item in visible" :key="item.key || item.to" class="nav-item">
        <router-link v-if="!item.children" :to="item.to" class="nav-link">
          <i :class="'bi bi-' + item.icon + ' me-2'"></i>{{ item.label }}
        </router-link>

        <template v-else>
          <button type="button" class="nav-link nav-group-toggle" :aria-expanded="open[item.key]"
                  @click="open[item.key] = !open[item.key]">
            <i :class="'bi bi-' + item.icon + ' me-2'"></i>{{ item.label }}
            <i :class="['bi bi-chevron-right ms-auto chev', { open: open[item.key] }]"></i>
          </button>
          <ul v-show="open[item.key]" class="nav flex-column nav-sub mt-1 gap-1">
            <li v-for="c in item.children" :key="c.to" class="nav-item">
              <router-link :to="c.to" class="nav-link">
                <i :class="'bi bi-' + c.icon + ' me-2'"></i>{{ c.label }}
              </router-link>
            </li>
          </ul>
        </template>
      </li>
    </ul>

    <div class="mt-auto small text-secondary">v1.0</div>
  </aside>
</template>