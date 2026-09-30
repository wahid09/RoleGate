<script setup>
import { ref } from 'vue'
import Sidebar from '../components/Sidebar.vue'
import Header from '../components/Header.vue'
import Footer from '../components/Footer.vue'

const collapsed = ref(false)
</script>

<template>
  <div class="app-shell" :class="{ collapsed }">
    <Sidebar />
    <div class="app-main">
      <Header @toggle="collapsed = !collapsed" />
      <main class="app-content">
        <router-view />
      </main>
      <Footer />
    </div>
  </div>
</template>