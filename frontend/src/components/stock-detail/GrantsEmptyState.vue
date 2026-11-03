<script setup>
import { Card, CardContent } from '@/components/ui/card'
</script>

<template>
  <Card class="border-dashed py-0">
    <CardContent class="flex min-h-56 flex-col items-center justify-center gap-3 p-6 text-center">
      <h3 class="text-lg font-medium">No grants or purchases added yet</h3>
      <p class="max-w-md text-sm text-muted-foreground">
        Use Add in the Acquisition timeline tab to record an RSU grant or ESPP purchase and track
        your shares.
      </p>
    </CardContent>
  </Card>
</template>
