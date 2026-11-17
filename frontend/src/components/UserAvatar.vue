<script setup>
import { computed } from 'vue'
import { hueFor, initials } from '../utils/avatar'

const props = defineProps({
  name: { type: String, default: '' },
  email: { type: String, default: '' },
  size: { type: Number, default: 40 },
  dimmed: { type: Boolean, default: false },
})

const text = computed(() => initials(props.name, props.email))
const style = computed(() => ({
  '--h': hueFor(props.email || props.name),
  width: `${props.size}px`,
  height: `${props.size}px`,
  fontSize: `${Math.round(props.size * 0.36)}px`,
}))
</script>

<template>
  <span :class="['avatar', { dimmed }]" :style="style" aria-hidden="true">{{ text }}</span>
</template>

<style scoped>
.avatar {
  flex: none;
  display: inline-grid;
  place-items: center;
  border-radius: 50%;
  font-weight: 600;
  letter-spacing: 0.02em;
  background: hsl(var(--h) 65% 91%);
  color: hsl(var(--h) 45% 28%);
  box-shadow: inset 0 0 0 1px hsl(var(--h) 55% 80%);
  user-select: none;
}
.avatar.dimmed {
  filter: grayscale(1);
  opacity: 0.6;
}
:global([data-bs-theme='dark']) .avatar {
  background: hsl(var(--h) 35% 24%);
  color: hsl(var(--h) 75% 86%);
  box-shadow: inset 0 0 0 1px hsl(var(--h) 35% 34%);
}
</style>
