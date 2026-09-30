<script setup>
import { useAuth } from '../stores/auth'
const auth = useAuth()
</script>

<template>
  <div>
    <h4 class="mb-3">My Profile</h4>
    <div class="card border-0 shadow-sm" style="max-width: 640px">
      <div class="card-body">
        <dl class="row mb-0">
          <dt class="col-sm-3">Name</dt>
          <dd class="col-sm-9">{{ auth.user?.full_name }}</dd>
          <dt class="col-sm-3">Email</dt>
          <dd class="col-sm-9">{{ auth.user?.email }}</dd>
          <dt class="col-sm-3">Roles</dt>
          <dd class="col-sm-9">
            <span v-for="r in auth.user?.roles" :key="r.id" class="badge text-bg-secondary me-1">{{ r.name }}</span>
          </dd>
          <dt class="col-sm-3">Permissions</dt>
          <dd class="col-sm-9">
            <span v-for="p in auth.user?.permissions" :key="p" class="badge text-bg-light border me-1 mb-1">{{ p }}</span>
            <span v-if="!auth.user?.permissions.length" class="text-muted">None</span>
          </dd>
        </dl>
      </div>
    </div>
  </div>
</template>