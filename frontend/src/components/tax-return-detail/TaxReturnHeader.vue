<script setup>
import { Settings } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

defineProps({
  year: {
    type: [Number, String],
    required: true,
  },
})

defineEmits(['edit-settings'])
</script>

<template>
  <div class="mb-8 flex items-center justify-between gap-4">
    <h1 class="text-3xl font-bold">Tax return {{ year }}</h1>
    <Button
      variant="outline"
      size="icon"
      aria-label="Edit tax return settings"
      @click="$emit('edit-settings')"
    >
      <Settings class="h-4 w-4" />
    </Button>
  </div>
</template>
