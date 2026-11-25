<script setup>
import { storeToRefs } from 'pinia'
import { useSettingsStore } from '@/stores/settings'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { formatNumber, NUMBER_LOCALES } from '@/lib/numberFormat.js'

const settingsStore = useSettingsStore()
const { theme, numberLocale, loadError, saveError, saving } = storeToRefs(settingsStore)

const themes = [
  {
    id: 'sage-slate',
    name: 'Sage & slate',
    description: 'Calm, approachable, and grounded.',
    colors: ['#F5F7F4', '#E8EEE9', '#FFFFFF', '#426B5A'],
  },
  {
    id: 'mist-blue',
    name: 'Mist blue',
    description: 'Clear and composed, with a cooler feel.',
    colors: ['#F5F8FA', '#E8F0F4', '#FFFFFF', '#386F88'],
  },
  {
    id: 'warm-stone',
    name: 'Warm stone',
    description: 'Soft and relaxed, with a warm accent.',
    colors: ['#F7F6F3', '#ECEAE5', '#FFFFFF', '#986B56'],
  },
  {
    id: 'midnight-slate',
    name: 'Midnight slate',
    description: 'Low glare, with a soft teal accent.',
    colors: ['#141D22', '#1B282E', '#202D33', '#83C5B6'],
  },
]
</script>

<template>
  <main class="p-8 w-full max-w-5xl">
    <h1 class="text-3xl font-bold mb-2">Settings</h1>
    <p class="text-muted-foreground mb-8">Choose the look and number format of this app.</p>

    <section aria-labelledby="color-theme-heading">
      <h2 id="color-theme-heading" class="text-xl font-semibold mb-1">Color theme</h2>
      <p class="text-sm text-muted-foreground mb-5">
        Your choice is saved for this app installation.
      </p>

      <RadioGroup
        :model-value="theme"
        :disabled="saving"
        aria-label="Color theme"
        class="grid gap-4 md:grid-cols-2 xl:grid-cols-4"
        @update:model-value="settingsStore.selectTheme"
      >
        <div
          v-for="option in themes"
          :key="option.id"
          :class="[
            'flex gap-3 rounded-xl border-2 bg-card p-5 shadow-sm transition-colors',
            theme === option.id
              ? 'border-primary ring-2 ring-primary/20'
              : 'border-border hover:border-primary/50',
          ]"
        >
          <RadioGroupItem :id="option.id" :value="option.id" :disabled="saving" class="mt-0.5" />
          <label :for="option.id" class="flex flex-1 cursor-pointer flex-col gap-2">
            <span class="font-semibold text-card-foreground">{{ option.name }}</span>
            <span class="text-sm text-muted-foreground">{{ option.description }}</span>
            <span class="mt-3 flex gap-2" aria-hidden="true">
              <span
                v-for="color in option.colors"
                :key="color"
                class="h-7 w-7 rounded-full border border-border"
                :style="{ backgroundColor: color }"
              />
            </span>
          </label>
        </div>
      </RadioGroup>
    </section>

    <section aria-labelledby="number-format-heading" class="mt-10">
      <h2 id="number-format-heading" class="text-xl font-semibold mb-1">Number format</h2>
      <p id="number-format-description" class="text-sm text-muted-foreground mb-5">
        Choose how numbers, amounts, and percentages are displayed. Saved for this app installation.
      </p>
      <label for="number-locale" class="block text-sm font-medium mb-2">Locale</label>
      <select
        id="number-locale"
        :value="numberLocale"
        :disabled="saving"
        aria-describedby="number-format-description"
        class="w-full max-w-md rounded-md border border-input bg-background px-3 py-2 text-sm"
        @change="settingsStore.selectNumberLocale($event.target.value)"
      >
        <option v-for="option in NUMBER_LOCALES" :key="option.id" :value="option.id">
          {{ option.name }} · {{ formatNumber(1234567.89, {}, option.id) }}
        </option>
      </select>
      <p class="mt-3 text-sm text-muted-foreground">
        Preview: {{ formatNumber(1234567.89) }} ·
        {{ formatNumber(1234.56, { style: 'currency', currency: 'EUR' }) }} ·
        {{ formatNumber(0.125, { style: 'percent', maximumFractionDigits: 1 }) }}
      </p>
    </section>

    <p v-if="saving" class="mt-4 text-sm text-muted-foreground" role="status">Saving settings…</p>
    <p v-if="loadError" class="mt-4 text-sm text-destructive" role="alert">{{ loadError }}</p>
    <p v-if="saveError" class="mt-4 text-sm text-destructive" role="alert">{{ saveError }}</p>
  </main>
</template>
