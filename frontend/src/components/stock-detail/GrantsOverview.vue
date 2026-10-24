<script setup>
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate, formatShares, grants, portfolio } from './mockPortfolio'
</script>

<template>
  <div class="space-y-4">
    <div>
      <h2 class="text-xl font-semibold">How your plans overlap</h2>
      <p class="mt-1 text-sm text-muted-foreground">
        Each annual grant has its own four-year vesting schedule.
      </p>
    </div>
    <Card class="gap-0 overflow-hidden py-0">
      <CardHeader class="p-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <CardTitle class="text-base">Your retention plans</CardTitle>
          <span class="text-xs text-muted-foreground"
            >25% after year one · 6.25% every three months after</span
          >
        </div>
      </CardHeader>
      <CardContent class="overflow-x-auto px-0">
        <table class="w-full min-w-[900px] text-sm">
          <caption class="sr-only">
            Sample grants, vested and remaining shares, next releases, and completion dates
          </caption>
          <thead class="border-y bg-muted/40 text-xs text-muted-foreground">
            <tr>
              <th scope="col" class="px-5 py-3 text-left font-medium">Grant</th>
              <th scope="col" class="px-4 py-3 text-right font-medium">Awarded</th>
              <th scope="col" class="px-4 py-3 text-right font-medium">Vested</th>
              <th scope="col" class="px-4 py-3 text-right font-medium">Still to vest</th>
              <th scope="col" class="px-4 py-3 text-left font-medium">Next release</th>
              <th scope="col" class="px-5 py-3 text-left font-medium">Fully vested</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="grant in grants" :key="grant.id" class="border-b">
              <th scope="row" class="min-w-64 px-5 py-5 text-left font-normal">
                <span class="inline-flex items-center gap-2 font-medium"
                  ><span
                    class="h-2.5 w-2.5 rounded-full"
                    :style="{ backgroundColor: grant.color }"
                  />{{ grant.name }}</span
                >
                <div
                  class="mt-3 flex h-1.5 overflow-hidden rounded-full bg-muted"
                  role="progressbar"
                  :aria-label="`${grant.name} vested`"
                  :aria-valuenow="grant.vested"
                  :aria-valuemax="grant.awarded"
                  :aria-valuemin="0"
                  :aria-valuetext="`${formatShares(grant.vested)} of ${formatShares(grant.awarded)} shares vested`"
                >
                  <div
                    class="rounded-full"
                    :style="{
                      width: `${(grant.vested / grant.awarded) * 100}%`,
                      backgroundColor: grant.color,
                    }"
                  />
                </div>
              </th>
              <td class="px-4 py-5 text-right tabular-nums">{{ formatShares(grant.awarded) }}</td>
              <td class="px-4 py-5 text-right tabular-nums">{{ formatShares(grant.vested) }}</td>
              <td class="px-4 py-5 text-right tabular-nums">{{ formatShares(grant.remaining) }}</td>
              <td class="px-4 py-5">
                <template v-if="grant.nextDate"
                  ><p class="font-medium">{{ formatShares(grant.nextShares) }} shares</p>
                  <p class="mt-1 whitespace-nowrap text-xs text-muted-foreground">
                    {{ formatDate(grant.nextDate) }}
                  </p></template
                ><span v-else class="rounded-full bg-primary/10 px-2 py-1 text-xs text-primary"
                  >Complete</span
                >
              </td>
              <td class="whitespace-nowrap px-5 py-5 text-muted-foreground">
                {{ formatDate(grant.completion) }}
              </td>
            </tr>
          </tbody>
          <tfoot class="bg-muted/30 font-medium">
            <tr>
              <th scope="row" class="px-5 py-4 text-left">All plans</th>
              <td class="px-4 py-4 text-right tabular-nums">
                {{ formatShares(portfolio.awarded) }}
              </td>
              <td class="px-4 py-4 text-right tabular-nums">
                {{ formatShares(portfolio.vested) }}
              </td>
              <td class="px-4 py-4 text-right tabular-nums">
                {{ formatShares(portfolio.unvested) }}
              </td>
              <td colspan="2" />
            </tr>
          </tfoot>
        </table>
      </CardContent>
    </Card>
    <div
      class="rounded-lg border border-dashed px-4 py-3 text-xs leading-relaxed text-muted-foreground"
    >
      Vested shares include shares already sold. Sales are tracked for the stock as a whole; no sale
      is attributed to a particular grant in this preview.
    </div>
  </div>
</template>
