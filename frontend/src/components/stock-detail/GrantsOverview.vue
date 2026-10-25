<script setup>
import { computed } from 'vue'
import { Trash2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { SCHEDULES, formatDate, formatShares, localDate, summarizeGrants } from './vesting.js'
import GrantsEmptyState from './GrantsEmptyState.vue'

const props = defineProps({
  grants: { type: Array, default: () => [] },
  today: { type: String, default: () => localDate() },
})
defineEmits(['delete'])
const portfolio = computed(() => summarizeGrants(props.grants, props.today))
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
      <h2 class="text-xl font-semibold">Your grants</h2>
      <p class="mt-1 text-sm text-muted-foreground">
        Review each grant’s vesting progress and remove any grants you need to replace.
      </p>
    </div>
    <GrantsEmptyState v-if="!grants.length" />
    <Card v-else class="gap-0 overflow-hidden py-0">
      <CardHeader class="p-5">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <CardTitle class="text-base"
            >{{ grants.length }} {{ grants.length === 1 ? 'grant' : 'grants' }}</CardTitle
          >
          <span class="text-xs text-muted-foreground">As of {{ formatDate(today) }}</span>
        </div>
      </CardHeader>
      <CardContent class="overflow-x-auto px-0">
        <table class="w-full min-w-[900px] text-sm">
          <caption class="sr-only">
            Entered grants, vested and remaining shares, next releases, and completion dates
          </caption>
          <thead class="border-y bg-muted/40 text-xs text-muted-foreground">
            <tr>
              <th scope="col" class="px-5 py-3 text-left font-medium">Grant</th>
              <th scope="col" class="px-4 py-3 text-right font-medium">Awarded</th>
              <th scope="col" class="px-4 py-3 text-right font-medium">Vested</th>
              <th scope="col" class="px-4 py-3 text-right font-medium">Still to vest</th>
              <th scope="col" class="px-4 py-3 text-left font-medium">Next release</th>
              <th scope="col" class="px-5 py-3 text-left font-medium">Fully vested</th>
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
                {{ formatDate(grant.completion) }}
              </td>
              <td class="px-5 py-5 text-right">
                <Button
                  variant="ghost"
                  class="text-destructive"
                  :aria-label="`Delete ${grant.title}`"
                  @click="$emit('delete', grant)"
                  ><Trash2 class="h-4 w-4" /> Delete</Button
                >
              </td>
            </tr>
          </tbody>
          <tfoot class="bg-muted/30 font-medium">
            <tr>
              <th scope="row" class="px-5 py-4 text-left">All grants</th>
              <td class="px-4 py-4 text-right tabular-nums">
                {{ formatShares(portfolio.awarded) }}
              </td>
              <td class="px-4 py-4 text-right tabular-nums">
                {{ formatShares(portfolio.vested) }}
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
    <p v-if="grants.length" class="text-xs text-muted-foreground">
      Vested quantities reflect the release dates you entered, before any sales. Deleting a grant
      also removes its releases from the vesting timeline.
    </p>
  </div>
</template>
