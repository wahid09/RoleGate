<script setup>
import { computed } from 'vue'
import { pageWindow, rangeLabel } from '../utils/pagination'

const props = defineProps({
  page: { type: Number, required: true },
  pageSize: { type: Number, required: true },
  total: { type: Number, required: true },
  sizes: { type: Array, default: () => [10, 25, 50, 100] },
})
const emit = defineEmits(['update:page', 'update:pageSize'])

const pages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const window_ = computed(() => pageWindow(props.page, pages.value))
const go = (p) => emit('update:page', Math.min(Math.max(1, p), pages.value))
</script>

<template>
  <div class="d-flex flex-wrap justify-content-between align-items-center gap-2">
    <div class="d-flex align-items-center gap-2">
      <span class="small text-muted">{{ rangeLabel(page, pageSize, total) }}</span>
      <select class="form-select form-select-sm w-auto" :value="pageSize" aria-label="Rows per page"
              @change="emit('update:pageSize', Number($event.target.value))">
        <option v-for="s in sizes" :key="s" :value="s">{{ s }} / page</option>
      </select>
    </div>
    <nav aria-label="Pages">
      <ul class="pagination pagination-sm mb-0">
        <li :class="['page-item', { disabled: page <= 1 }]">
          <button class="page-link" @click="go(page - 1)">Prev</button>
        </li>
        <template v-for="(p, i) in window_" :key="i">
          <li v-if="p === null" class="page-item disabled"><span class="page-link">…</span></li>
          <li v-else :class="['page-item', { active: p === page }]">
            <button class="page-link" @click="go(p)">{{ p }}</button>
          </li>
        </template>
        <li :class="['page-item', { disabled: page >= pages }]">
          <button class="page-link" @click="go(page + 1)">Next</button>
        </li>
      </ul>
    </nav>
  </div>
</template>
