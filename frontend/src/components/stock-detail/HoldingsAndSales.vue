<script setup>
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { activity, formatDate, formatShares, portfolio } from './mockPortfolio'

const time = (date) => Date.parse(`${date}T00:00:00Z`)
const start = time(activity[0].date)
const end = time(portfolio.asOf)
const x = (date) => 55 + ((time(date) - start) / (end - start)) * 930
const y = (balance) => 255 - (balance / 2800) * 220
const points = activity.map((event) => ({ ...event, x: x(event.date), y: y(event.balance) }))
const line = `M ${points[0].x} ${points[0].y} ${points
  .slice(1)
  .map((point) => `H ${point.x} V ${point.y}`)
  .join(' ')} H ${x(portfolio.asOf)}`
const area = `${line} L ${x(portfolio.asOf)} 255 L ${points[0].x} 255 Z`
const axisDates = [
  '2025-01-01',
  '2025-04-01',
  '2025-07-01',
  '2025-10-01',
  '2026-01-01',
  '2026-04-01',
  '2026-07-01',
  '2026-10-01',
]
const dateLabel = (date) =>
  new Intl.DateTimeFormat('en-GB', { month: 'short', year: '2-digit', timeZone: 'UTC' }).format(
    new Date(`${date}T00:00:00Z`),
  )
const proceeds = (amount) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(amount)
const ledger = [...activity].reverse()
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h2 class="text-xl font-semibold">What you held, and when</h2>
        <p class="mt-1 text-sm text-muted-foreground">
          Vesting adds shares. Sales reduce your available balance.
        </p>
      </div>
      <slot name="actions" />
    </div>
    <Card class="gap-0 py-0">
      <CardHeader class="flex flex-row flex-wrap items-center justify-between gap-3 p-5 pb-0">
        <CardTitle class="text-base">Vested, unsold shares</CardTitle>
        <div class="flex gap-4 text-xs text-muted-foreground">
          <span class="inline-flex items-center gap-2"
            ><span class="h-0.5 w-4 bg-primary" /> Shares held</span
          >
          <span class="inline-flex items-center gap-2"
            ><span class="h-2.5 w-2.5 rounded-full border-2 border-destructive" /> Sale</span
          >
        </div>
      </CardHeader>
      <CardContent class="p-5">
        <div class="overflow-x-auto">
          <svg
            viewBox="0 0 1100 310"
            class="min-w-[700px] w-full"
            role="img"
            aria-labelledby="holdings-chart-title holdings-chart-description"
          >
            <title id="holdings-chart-title">Holdings from January 2025 to October 2026</title>
            <desc id="holdings-chart-description">
              A step chart starting with 940 shares and ending with 1,860 held shares. Upward steps
              are vesting events and downward steps are sales. Exact dates and balances are in the
              activity ledger below.
            </desc>
            <g v-for="tick in [0, 800, 1600, 2400]" :key="tick">
              <line
                x1="55"
                x2="985"
                :y1="y(tick)"
                :y2="y(tick)"
                class="stroke-border"
                stroke-dasharray="3 4"
              />
              <text
                x="44"
                :y="y(tick) + 4"
                text-anchor="end"
                class="fill-muted-foreground text-[11px]"
              >
                {{ formatShares(tick) }}
              </text>
            </g>
            <text x="55" y="18" class="fill-muted-foreground text-[11px]">Shares held</text>
            <path :d="area" class="fill-primary/10" />
            <path
              :d="line"
              fill="none"
              class="stroke-primary"
              stroke-width="2.5"
              stroke-linejoin="round"
            />
            <g v-for="point in points.filter((event) => event.type === 'sale')" :key="point.id">
              <circle
                :cx="point.x"
                :cy="point.y"
                r="5"
                class="fill-card stroke-destructive"
                stroke-width="2"
              />
              <title>
                {{ formatDate(point.date) }}: sold {{ formatShares(-point.change) }} shares;
                {{ formatShares(point.balance) }} held
              </title>
            </g>
            <circle :cx="x(portfolio.asOf)" :cy="y(portfolio.held)" r="4" class="fill-primary" />
            <text x="1000" :y="y(portfolio.held) - 3" class="fill-primary text-sm font-semibold">
              {{ formatShares(portfolio.held) }}
            </text>
            <text x="1000" :y="y(portfolio.held) + 14" class="fill-muted-foreground text-[11px]">
              held today
            </text>
            <text
              v-for="date in axisDates"
              :key="date"
              :x="x(date)"
              y="283"
              text-anchor="middle"
              class="fill-muted-foreground text-[11px]"
            >
              {{ dateLabel(date) }}
            </text>
          </svg>
        </div>
        <div class="mt-2 flex flex-wrap gap-x-8 gap-y-2 border-t pt-4 text-sm">
          <p>
            <span class="text-muted-foreground">Lifetime vested</span>
            <span class="ml-2 font-medium tabular-nums">{{ formatShares(portfolio.vested) }}</span>
          </p>
          <p>
            <span class="text-muted-foreground">Lifetime sold</span>
            <span class="ml-2 font-medium tabular-nums">{{ formatShares(portfolio.sold) }}</span>
          </p>
          <p>
            <span class="text-muted-foreground">Still held</span>
            <span class="ml-2 font-medium tabular-nums text-primary">{{
              formatShares(portfolio.held)
            }}</span>
          </p>
        </div>
      </CardContent>
    </Card>

    <Card class="gap-0 overflow-hidden py-0">
      <CardHeader class="p-5">
        <CardTitle class="text-base">Activity ledger</CardTitle>
        <p class="text-xs text-muted-foreground">
          Since January 2025 · Newest first · Sample proceeds in USD, before fees
        </p>
      </CardHeader>
      <CardContent class="overflow-x-auto px-0">
        <table class="w-full min-w-[620px] text-sm">
          <caption class="sr-only">
            Sample vesting and sale activity with resulting share balances
          </caption>
          <thead class="border-y bg-muted/40 text-xs text-muted-foreground">
            <tr>
              <th scope="col" class="px-5 py-3 text-left font-medium">Date</th>
              <th scope="col" class="px-5 py-3 text-left font-medium">Event</th>
              <th scope="col" class="px-5 py-3 text-right font-medium">Share change</th>
              <th scope="col" class="px-5 py-3 text-right font-medium">Balance</th>
              <th scope="col" class="px-5 py-3 text-right font-medium">Sale proceeds</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="event in ledger" :key="event.id" class="border-b last:border-0">
              <td class="whitespace-nowrap px-5 py-3 text-muted-foreground">
                {{ formatDate(event.date) }}
              </td>
              <td class="px-5 py-3">
                <span class="inline-flex items-center gap-2"
                  ><span
                    class="h-2 w-2 rounded-full"
                    :class="
                      event.type === 'sale'
                        ? 'bg-destructive'
                        : event.type === 'vesting'
                          ? 'bg-primary'
                          : 'bg-muted-foreground'
                    "
                  />{{ event.label }}</span
                >
              </td>
              <td
                class="px-5 py-3 text-right font-medium tabular-nums"
                :class="
                  event.change < 0
                    ? 'text-destructive'
                    : event.change > 0
                      ? 'text-primary'
                      : 'text-muted-foreground'
                "
              >
                {{
                  event.change === 0
                    ? '—'
                    : `${event.change > 0 ? '+' : '−'}${formatShares(Math.abs(event.change))}`
                }}
              </td>
              <td class="px-5 py-3 text-right tabular-nums">{{ formatShares(event.balance) }}</td>
              <td class="px-5 py-3 text-right tabular-nums text-muted-foreground">
                {{ event.proceeds ? proceeds(event.proceeds) : '—' }}
              </td>
            </tr>
          </tbody>
        </table>
      </CardContent>
    </Card>
  </div>
</template>
