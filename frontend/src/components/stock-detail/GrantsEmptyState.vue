<script setup>
import { Card, CardContent } from '@/components/ui/card'
</script>

<template>
  <Card class="border-dashed py-0">
    <CardContent class="flex min-h-56 flex-col items-center justify-center gap-3 p-6 text-center">
      <h3 class="text-lg font-medium">No grants added yet</h3>
      <p class="max-w-md text-sm text-muted-foreground">
        Use Add grant at the top of the page to see your grants, vesting schedules, and progress.
      </p>
    </CardContent>
  </Card>
</template>
