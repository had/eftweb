<script setup>
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

defineProps({
  estimate: { type: Object, default: null },
  estimationLoading: Boolean,
  estimationError: { type: String, default: '' },
})

const currency = new Intl.NumberFormat('en-GB', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const formatAmount = (amount) => amount == null ? '—' : currency.format(amount)
</script>

<template>
  <Card class="mb-6 w-full">
    <CardHeader><CardTitle>Tax summary</CardTitle></CardHeader>
    <CardContent class="space-y-4" aria-live="polite" :aria-busy="estimationLoading">
      <p v-if="estimationError" class="text-sm text-destructive">{{ estimationError }}</p>
      <div class="grid gap-4 sm:grid-cols-2">
        <div>
          <p class="text-sm text-muted-foreground">Net taxes</p>
          <div v-if="estimationLoading" class="mt-1 h-7 w-28 animate-pulse rounded bg-muted" aria-label="Loading net taxes" />
          <p v-else class="mt-1 text-lg font-medium">{{ formatAmount(estimate?.net_taxes) }}</p>
        </div>
        <div>
          <p class="text-sm text-muted-foreground">Net social taxes</p>
          <div v-if="estimationLoading" class="mt-1 h-7 w-28 animate-pulse rounded bg-muted" aria-label="Loading net social taxes" />
          <p v-else class="mt-1 text-lg font-medium">{{ formatAmount(estimate?.net_social_taxes) }}</p>
        </div>
      </div>
      <p class="text-sm text-muted-foreground">
        Partial estimate using supported statement fields only. Salary withholding and supplementary pension contributions are excluded.
      </p>
    </CardContent>
  </Card>
</template>
