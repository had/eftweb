<script setup>
import { computed, watch } from 'vue'
import { useStockQuotesStore } from '@/stores/stockQuotes'
import { formatDate } from '@/components/stock-detail/vesting.js'
import { formatQuoteTimestamp, formatStockValue } from '@/lib/stockQuotes.js'

const props = defineProps({ stock: { type: Object, default: null }, compact: Boolean })
const quotesStore = useStockQuotesStore()
const entry = computed(() => quotesStore.forSymbol(props.stock?.symbol))
watch(
  [() => props.stock?.id, () => props.stock?.symbol],
  () => {
    void quotesStore.load(props.stock)
  },
  { immediate: true },
)
</script>

<template>
  <div class="space-y-1" :class="compact ? 'text-xl' : 'text-sm'" aria-live="polite">
    <p v-if="entry.loading && !entry.quote?.price" role="status" class="text-muted-foreground">
      Loading price…
    </p>
    <template v-else-if="entry.quote?.price">
      <p class="flex flex-wrap items-baseline gap-x-2 gap-y-1" :class="compact && 'justify-end'">
        <span class="font-semibold tabular-nums"
          >{{ formatStockValue(1, entry.quote.price) }} USD</span
        >
        <span class="text-xs text-muted-foreground"
          >{{ entry.quote.stale ? 'Cached price' : 'Latest close'
          }}{{ entry.quote.quote_date ? ` · ${formatDate(entry.quote.quote_date)}` : '' }}</span
        >
      </p>
      <p v-if="!compact && entry.quote.fetched_at" class="text-xs text-muted-foreground">
        {{ entry.quote.stale ? 'Cached quote retrieved' : 'Retrieved' }}
        {{ formatQuoteTimestamp(entry.quote.fetched_at) }}
      </p>
    </template>
    <p v-else class="text-muted-foreground" :title="entry.error || 'No quote available.'">
      Price unavailable
    </p>
  </div>
</template>
