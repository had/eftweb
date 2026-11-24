<script setup>
import { Info } from 'lucide-vue-next'
import { TooltipContent, TooltipPortal, TooltipRoot, TooltipTrigger } from 'reka-ui'

defineProps({ label: { type: String, required: true } })
</script>

<template>
  <TooltipRoot>
    <TooltipTrigger as-child>
      <button
        type="button"
        :aria-label="label"
        class="inline-flex size-7 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Info class="size-4" aria-hidden="true" />
      </button>
    </TooltipTrigger>
    <TooltipPortal>
      <TooltipContent
        side="top"
        :side-offset="6"
        class="z-[60] max-w-xs space-y-2 rounded-md border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md"
      >
        <slot />
      </TooltipContent>
    </TooltipPortal>
  </TooltipRoot>
</template>
