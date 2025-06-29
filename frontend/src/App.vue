<script setup>
import { RouterView } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
</script>

<template>
  <div class="layout">
    <NavBar />
    <RouterView class="mainview" />
  </div>
</template>
