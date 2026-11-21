<script setup>
import { computed } from 'vue'
import { Pencil, Trash2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  SCHEDULES,
  formatDate,
  formatShares,
  localDate,
  summarizeGrants,
  summarizePortfolio,
} from './vesting.js'
import GrantsEmptyState from './GrantsEmptyState.vue'
import { purchaseColor } from './acquisitions.js'

const props = defineProps({
  grants: { type: Array, default: () => [] },
  purchases: { type: Array, default: () => [] },
  busy: Boolean,
  today: { type: String, default: () => localDate() },
})
defineEmits(['delete', 'delete-purchase', 'edit-grant'])
const portfolio = computed(() => summarizePortfolio(props.grants, props.purchases, props.today))
const rows = computed(() =>
  props.grants.map((grant) => {
    const summary = summarizeGrants([grant], props.today)
    return {
      ...grant,
      vested: summary.vested,
      remaining: summary.unvested,
      nextRelease: summary.nextRelease,
      completion: grant.vestings.reduce(
        (last, release) => (release.date > last ? release.date : last),
        '',
      ),
      scheduleLabel:
        SCHEDULES.find((schedule) => schedule.value === grant.scheduleType)?.label ||
        'Custom schedule',
    }
  }),
)
</script>

<template>
  <div class="space-y-4">
    <div>
      <h2 class="text-xl font-semibold">Your plans &amp; purchases</h2>
      <p class="mt-1 text-sm text-muted-foreground">
        Review RSU vesting progress and completed stock purchases.
      </p>
    </div>
    <GrantsEmptyState v-if="!grants.length && !purchases.length" />
    <Card v-else class="gap-0 overflow-hidden py-0">
      <CardHeader class="p-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <CardTitle class="text-base"
            >{{ grants.length }} {{ grants.length === 1 ? 'grant' : 'grants' }} ·
            {{ purchases.length }}
            {{ purchases.length === 1 ? 'purchase' : 'purchases' }}</CardTitle
          >
          <span class="text-xs text-muted-foreground">As of {{ formatDate(today) }}</span>
        </div>
      </CardHeader>
      <CardContent class="overflow-x-auto px-0">
        <table class="w-full min-w-[900px] text-sm">
          <caption class="sr-only">
            Entered grants and purchases, acquired and remaining shares, next releases, and
            completion dates
          </caption>
          <thead class="border-y bg-muted/40 text-xs text-muted-foreground">
            <tr>
              <th scope="col" class="px-5 py-3 text-left font-medium">Plan / purchase</th>
              <th scope="col" class="px-4 py-3 text-right font-medium">Total shares</th>
              <th scope="col" class="px-4 py-3 text-right font-medium">Acquired</th>
              <th scope="col" class="px-4 py-3 text-right font-medium">Still to vest</th>
              <th scope="col" class="px-4 py-3 text-left font-medium">Next release</th>
              <th scope="col" class="px-5 py-3 text-left font-medium">Completion date</th>
              <th scope="col" class="px-5 py-3 text-right font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="grant in rows" :key="grant.id" class="border-b">
              <th scope="row" class="min-w-64 px-5 py-5 text-left font-normal">
                <span class="inline-flex items-center gap-2 font-medium"
                  ><span
                    class="h-2.5 w-2.5 rounded-full"
                    :style="{ backgroundColor: grant.color }"
                  />{{ grant.title }}</span
                >
                <p class="mt-1 text-xs text-muted-foreground">
                  Granted {{ formatDate(grant.grantDate) }}
                </p>
                <p class="mt-1 text-xs text-muted-foreground">
                  Grant number: {{ grant.grantNumber || 'Not entered' }}
                </p>
                <p class="mt-1 text-xs text-muted-foreground">
                  Shareholder approval:
                  {{ grant.approvalDate ? formatDate(grant.approvalDate) : 'Not entered' }}
                </p>
                <p class="mt-1 text-xs text-muted-foreground">
                  Taxpayer:
                  {{
                    grant.taxpayerRole === 'taxpayer1'
                      ? 'Taxpayer 1'
                      : grant.taxpayerRole === 'taxpayer2'
                        ? 'Taxpayer 2'
                        : 'Not assigned'
                  }}
                </p>
                <p class="mt-1 text-xs text-muted-foreground">
                  {{ grant.scheduleLabel }}{{ grant.customized ? ' · Customized' : '' }}
                </p>
                <div
                  class="mt-3 flex h-1.5 overflow-hidden rounded-full bg-muted"
                  role="progressbar"
                  :aria-label="`${grant.title} vested`"
                  :aria-valuenow="grant.vested"
                  :aria-valuemax="grant.quantity"
                  :aria-valuemin="0"
                  :aria-valuetext="`${formatShares(grant.vested)} of ${formatShares(grant.quantity)} shares vested`"
                >
                  <div
                    class="rounded-full"
                    :style="{
                      width: `${(grant.vested / grant.quantity) * 100}%`,
                      backgroundColor: grant.color,
                    }"
                  />
                </div>
              </th>
              <td class="px-4 py-5 text-right tabular-nums">{{ formatShares(grant.quantity) }}</td>
              <td class="px-4 py-5 text-right tabular-nums">{{ formatShares(grant.vested) }}</td>
              <td class="px-4 py-5 text-right tabular-nums">{{ formatShares(grant.remaining) }}</td>
              <td class="px-4 py-5">
                <template v-if="grant.nextRelease"
                  ><p class="font-medium">{{ formatShares(grant.nextRelease.quantity) }} shares</p>
                  <p class="mt-1 whitespace-nowrap text-xs text-muted-foreground">
                    {{ formatDate(grant.nextRelease.date) }}
                  </p></template
                ><span v-else class="rounded-full bg-primary/10 px-2 py-1 text-xs text-primary"
                  >Complete</span
                >
              </td>
              <td class="whitespace-nowrap px-5 py-5 text-muted-foreground">
                {{ grant.completion ? formatDate(grant.completion) : 'Not scheduled' }}
              </td>
              <td class="px-5 py-5 text-right">
                <Button
                  variant="ghost"
                  :disabled="busy"
                  :aria-label="`Edit ${grant.title}`"
                  @click="$emit('edit-grant', grant)"
                >
                  <Pencil class="h-4 w-4" /> Edit
                </Button>
                <Button
                  variant="ghost"
                  :disabled="busy"
                  class="text-destructive"
                  :aria-label="`Delete ${grant.title}`"
                  @click="$emit('delete', grant)"
                  ><Trash2 class="h-4 w-4" /> Delete</Button
                >
              </td>
            </tr>
            <tr v-for="purchase in purchases" :key="`purchase-${purchase.id}`" class="border-b">
              <th scope="row" class="min-w-64 px-5 py-5 text-left font-normal">
                <span class="inline-flex items-center gap-2 font-medium"
                  ><span
                    class="h-2.5 w-2.5 rounded-full"
                    :style="{ backgroundColor: purchaseColor }"
                  />{{ purchase.planName }}</span
                >
                <p class="mt-1 text-xs text-muted-foreground">
                  Purchased {{ formatDate(purchase.purchaseDate) }}
                </p>
              </th>
              <td class="px-4 py-5 text-right tabular-nums">
                {{ formatShares(purchase.quantity) }}
              </td>
              <td class="px-4 py-5 text-right tabular-nums">
                {{ formatShares(purchase.quantity) }}
              </td>
              <td class="px-4 py-5 text-right text-muted-foreground">—</td>
              <td class="px-4 py-5 text-muted-foreground">—</td>
              <td class="whitespace-nowrap px-5 py-5 text-muted-foreground">
                {{ formatDate(purchase.purchaseDate) }}
              </td>
              <td class="px-5 py-5 text-right">
                <Button
                  variant="ghost"
                  class="text-destructive"
                  :disabled="busy"
                  :aria-label="`Delete ${purchase.planName} purchase on ${formatDate(purchase.purchaseDate)}`"
                  @click="$emit('delete-purchase', purchase)"
                  ><Trash2 class="h-4 w-4" /> Delete</Button
                >
              </td>
            </tr>
          </tbody>
          <tfoot class="bg-muted/30 font-medium">
            <tr>
              <th scope="row" class="px-5 py-4 text-left">All plans &amp; purchases</th>
              <td class="px-4 py-4 text-right tabular-nums">
                {{ formatShares(portfolio.total) }}
              </td>
              <td class="px-4 py-4 text-right tabular-nums">
                {{ formatShares(portfolio.acquired) }}
              </td>
              <td class="px-4 py-4 text-right tabular-nums">
                {{ formatShares(portfolio.unvested) }}
              </td>
              <td colspan="3" />
            </tr>
          </tfoot>
        </table>
      </CardContent>
    </Card>
    <p v-if="grants.length || purchases.length" class="text-xs text-muted-foreground">
      Acquired quantities reflect vestings and purchases before any sales. Deleting a grant or
      purchase also removes its acquisitions from the timeline.
    </p>
  </div>
</template>
