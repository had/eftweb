<script setup>
defineProps({
  title: {
    type: String,
    required: true,
  },
})
</script>

<template>
  <div class="p-8">
    <h1 class="text-3xl font-bold mb-8" style="font-size: 32px">{{ title }}</h1>
    <slot />
  </div>
</template>
