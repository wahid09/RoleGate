<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'

defineEmits(['toggle'])
const auth = useAuth()
const router = useRouter()
const roleNames = computed(() => auth.user?.roles.map((r) => r.name).join(', '))

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <header class="navbar bg-white border-bottom px-3 sticky-top">
    <button class="btn btn-light" @click="$emit('toggle')">
      <i class="bi bi-list fs-5"></i>
    </button>

    <div class="dropdown ms-auto">
      <a href="#" class="d-flex align-items-center text-decoration-none text-dark dropdown-toggle"
         data-bs-toggle="dropdown">
        <i class="bi bi-person-circle fs-4 me-2"></i>
        <span class="d-none d-sm-inline">{{ auth.user?.full_name }}</span>
      </a>
      <ul class="dropdown-menu dropdown-menu-end shadow-sm">
        <li class="px-3 py-1 small text-muted">{{ roleNames }}</li>
        <li><hr class="dropdown-divider" /></li>
        <li><router-link class="dropdown-item" to="/profile">Profile</router-link></li>
        <li><a class="dropdown-item text-danger" href="#" @click.prevent="logout">Logout</a></li>
      </ul>
    </div>
  </header>
</template>