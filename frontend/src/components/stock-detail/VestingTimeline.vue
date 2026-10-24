<script setup>
import { computed, ref } from 'vue'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate, formatShares, grants, portfolio, quarters } from './mockPortfolio'

const selectedId = ref('2027-Q1')
const selectedQuarter = computed(() => quarters.find((quarter) => quarter.id === selectedId.value))
const contributions = computed(() =>
  grants
    .map((grant, index) => ({
      ...grant,
      shares: selectedQuarter.value.shares[index],
    }))
    .filter((grant) => grant.shares > 0),
)

const left = 52
const baseline = 254
const step = 49
const scale = 0.17
const todayX = left + 8 * step
const bars = quarters.map((quarter, index) => {
  let stacked = 0
  return {
    ...quarter,
    x: left + index * step,
    segments: quarter.shares
      .map((shares, grantIndex) => {
        stacked += shares
        return {
          shares,
          y: baseline - stacked * scale,
          height: shares * scale,
          color: grants[grantIndex].color,
        }
      })
      .filter((segment) => segment.shares > 0),
  }
})
const yearLabels = ['2025', '2026', '2027', '2028', '2029', '2030']
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 class="text-xl font-semibold">When shares become yours</h2>
        <p class="mt-1 text-sm text-muted-foreground">
          Quarterly releases across all awarded plans, past and future.
        </p>
      </div>
      <p class="text-sm text-muted-foreground">
        Next release
        <span class="font-medium text-foreground"
          >{{ formatShares(portfolio.nextRelease.shares) }} shares</span
        >
        · {{ formatDate(portfolio.nextRelease.date) }}
      </p>
    </div>

    <Card class="gap-0 py-0">
      <CardHeader class="gap-3 p-5 pb-0">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <CardTitle class="text-base">Vesting by quarter</CardTitle>
          <div class="flex gap-4 text-xs text-muted-foreground">
            <span class="inline-flex items-center gap-2"
              ><span class="h-3 w-3 rounded-sm bg-primary" /> Vested</span
            >
            <span class="inline-flex items-center gap-2"
              ><span class="h-3 w-3 rounded-sm border-2 border-primary" /> Scheduled</span
            >
          </div>
        </div>
        <div
          class="flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground"
          aria-label="Grant legend"
        >
          <span v-for="grant in grants" :key="grant.id" class="inline-flex items-center gap-2"
            ><span class="h-2.5 w-2.5 rounded-full" :style="{ backgroundColor: grant.color }" />{{
              grant.id
            }}
            plan</span
          >
        </div>
      </CardHeader>
      <CardContent class="p-5">
        <div class="overflow-x-auto pb-2">
          <svg
            viewBox="0 0 1100 318"
            class="min-w-[850px] w-full"
            role="group"
            aria-labelledby="vesting-chart-title vesting-chart-description"
          >
            <title id="vesting-chart-title">Quarterly vesting timeline</title>
            <desc id="vesting-chart-description">
              Filled stacked bars show vested shares, outlined bars show scheduled releases. Select
              a quarter for its grant breakdown. The quarter selector below provides the same
              information.
            </desc>
            <rect
              :x="todayX"
              y="29"
              :width="1088 - todayX"
              height="225"
              rx="4"
              class="fill-muted/40"
            />
            <g v-for="tick in [0, 400, 800, 1200]" :key="tick">
              <line
                :x1="left"
                x2="1088"
                :y1="baseline - tick * scale"
                :y2="baseline - tick * scale"
                class="stroke-border"
                stroke-dasharray="3 4"
              />
              <text
                :x="left - 10"
                :y="baseline - tick * scale + 4"
                text-anchor="end"
                class="fill-muted-foreground text-[11px]"
              >
                {{ formatShares(tick) }}
              </text>
            </g>
            <text :x="left" y="18" class="fill-muted-foreground text-[11px]">Shares</text>
            <text x="1088" y="18" text-anchor="end" class="fill-muted-foreground text-[11px]">
              Awarded grants only
            </text>
            <g
              v-for="bar in bars"
              :key="bar.id"
              class="cursor-pointer"
              @click="selectedId = bar.id"
            >
              <title>
                {{ bar.quarter }} {{ bar.year }}: {{ formatShares(bar.total) }}
                {{ bar.scheduled ? 'scheduled' : 'vested' }} shares
              </title>
              <rect
                :x="bar.x + 2"
                y="30"
                :width="step - 4"
                height="229"
                rx="4"
                :class="
                  bar.id === selectedId ? 'fill-primary/10' : 'fill-transparent hover:fill-muted'
                "
              />
              <rect
                v-for="(segment, index) in bar.segments"
                :key="index"
                :x="bar.x + 10"
                :y="segment.y"
                width="29"
                :height="Math.max(segment.height - 2, 1)"
                rx="2"
                :fill="segment.color"
                :fill-opacity="bar.scheduled ? 0.08 : 1"
                :stroke="segment.color"
                :stroke-width="bar.scheduled ? 1.5 : 0"
              />
              <text
                :x="bar.x + step / 2"
                y="277"
                text-anchor="middle"
                class="fill-muted-foreground text-[11px]"
              >
                {{ bar.quarter }}
              </text>
            </g>
            <line
              :x1="todayX"
              :x2="todayX"
              y1="30"
              y2="260"
              class="stroke-foreground"
              stroke-width="1.5"
              stroke-dasharray="4 4"
            />
            <text
              :x="todayX - 8"
              y="41"
              text-anchor="end"
              class="fill-foreground text-[11px] font-semibold"
            >
              Today
            </text>
            <text
              v-for="(year, index) in yearLabels"
              :key="year"
              :x="left + (index * 4 + (index === 5 ? 0.5 : 2)) * step"
              y="306"
              text-anchor="middle"
              class="fill-foreground text-xs font-medium"
            >
              {{ year }}
            </text>
          </svg>
        </div>

        <div class="mt-4 grid gap-5 border-t pt-5 md:grid-cols-[1fr_1.3fr]">
          <div>
            <label
              for="vesting-quarter"
              class="text-xs font-medium uppercase tracking-wide text-muted-foreground"
              >Explore a quarter</label
            >
            <select
              id="vesting-quarter"
              v-model="selectedId"
              class="mt-2 block rounded-md border bg-background px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-ring"
            >
              <option v-for="quarter in quarters" :key="quarter.id" :value="quarter.id">
                {{ quarter.quarter }} {{ quarter.year }}
              </option>
            </select>
            <div aria-live="polite" class="mt-3">
              <p class="text-2xl font-semibold tabular-nums">
                {{ formatShares(selectedQuarter.total) }}
                <span class="text-sm font-normal text-muted-foreground"
                  >shares {{ selectedQuarter.scheduled ? 'scheduled' : 'vested' }}</span
                >
              </p>
              <p class="mt-1 text-xs text-muted-foreground">
                Release date: {{ formatDate(selectedQuarter.date) }}
              </p>
            </div>
          </div>
          <ul class="space-y-2 text-sm" aria-label="Selected quarter grant breakdown">
            <li
              v-for="grant in contributions"
              :key="grant.id"
              class="flex items-center justify-between gap-3 rounded-md bg-muted/50 px-3 py-2"
            >
              <span class="inline-flex items-center gap-2"
                ><span
                  class="h-2.5 w-2.5 rounded-full"
                  :style="{ backgroundColor: grant.color }"
                />{{ grant.name }}</span
              >
              <span class="font-medium tabular-nums">{{ formatShares(grant.shares) }}</span>
            </li>
          </ul>
        </div>
      </CardContent>
    </Card>
    <p class="text-xs text-muted-foreground">
      Sales do not change this timeline. It shows when shares vest; the Holdings &amp; sales tab
      shows what remains held.
    </p>
  </div>
</template>
