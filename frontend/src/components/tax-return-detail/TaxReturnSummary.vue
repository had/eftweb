<script setup>
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
</script>

<template>
  <Card class="mb-6 w-full">
    <CardHeader><CardTitle>Tax summary</CardTitle></CardHeader>
    <CardContent class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <div>
        <p class="text-sm text-muted-foreground">Net income</p>
        <p class="mt-1 text-lg font-medium">—</p>
      </div>
      <div>
        <p class="text-sm text-muted-foreground">Reference taxable revenue</p>
        <p class="mt-1 text-lg font-medium">—</p>
      </div>
      <div>
        <p class="text-sm text-muted-foreground">Average tax rate</p>
        <p class="mt-1 text-lg font-medium">—</p>
      </div>
      <div>
        <p class="text-sm text-muted-foreground">Marginal tax rate</p>
        <p class="mt-1 text-lg font-medium">— % from next bucket</p>
      </div>
    </CardContent>
  </Card>
</template>
