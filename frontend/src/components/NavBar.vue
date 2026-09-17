<script setup>
import { ref, watch, computed } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useFamilyStore } from '@/stores/family'
import { Separator } from '@/components/ui/separator'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { ChevronDown, ChevronRight } from 'lucide-vue-next'
import axios from 'axios'

const route = useRoute()
const router = useRouter()
const familyStore = useFamilyStore()
const taxYears = ref([])
const isTaxExpanded = ref(false)

const isFamilySelected = computed(() => !!familyStore.familyId)

const isCurrentPath = (viewPath) => {
  return route.path === viewPath
}

const exitFamily = () => {
  familyStore.clearCurrentFamily()
  router.push('/families')
}

// Watch for family changes and fetch tax years
watch(
  [() => familyStore.familyId, () => familyStore.taxReturnsVersion],
  async ([newId]) => {
    if (newId) {
      try {
        const response = await axios.get(`/api/families/${newId}/tax-returns`)
        taxYears.value = response.data
          .map((ts) => ({
            year: ts.year,
            id: ts.id,
          }))
          .sort((a, b) => b.year - a.year) // Sort descending by year
      } catch (error) {
        console.error('Failed to fetch tax years:', error)
        taxYears.value = []
      }
    } else {
      taxYears.value = []
      isTaxExpanded.value = false
    }
  },
  { immediate: true }
)
</script>

<template>
  <nav class="navbar">
    <div class="navsection">
      <RouterLink to="/" class="logo py-4 self-center">Easy French Tax</RouterLink>

      <!-- Family Section -->
      <Separator class="my-2 mx-2" />
      <div class="px-3 py-2">
        <RouterLink
          v-if="!isFamilySelected"
          to="/families"
          class="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          Select a family →
        </RouterLink>
        <div v-else class="flex items-center justify-between gap-2">
          <RouterLink
            to="/family"
            class="min-w-0 flex-1 text-sm font-medium truncate hover:text-primary transition-colors cursor-pointer"
            :title="familyStore.familyName"
          >
            {{ familyStore.familyName }}
          </RouterLink>
          <button
            type="button"
            class="text-xs text-blue-600 hover:text-blue-800 cursor-pointer"
            @click="exitFamily"
          >
            exit
          </button>
        </div>
      </div>
      <Separator class="my-2 mx-2" />

      <!-- Navigation Links -->
      <div class="flex flex-col mt-2">
        <Collapsible v-model:open="isTaxExpanded">
          <CollapsibleTrigger
            :class="[
              'item flex items-center justify-between w-full',
              isCurrentPath('/tax-returns') ? 'background-color:#000 border-l-2 border-l-gray-500' : '',
              !isFamilySelected ? 'opacity-50 cursor-not-allowed' : '',
            ]"
            :disabled="!isFamilySelected"
            @click.prevent="
              () => {
                if (!isFamilySelected) return
                router.push('/tax-returns')
                if (taxYears.length > 0) {
                  isTaxExpanded = !isTaxExpanded
                }
              }
            "
          >
            <span>Tax Returns</span>
            <component
              :is="isTaxExpanded ? ChevronDown : ChevronRight"
              v-if="isFamilySelected && taxYears.length > 0"
              class="h-4 w-4"
            />
          </CollapsibleTrigger>

          <CollapsibleContent v-if="isFamilySelected">
            <span
              v-for="taxYear in taxYears"
              :key="taxYear.id"
              class="item pl-8 text-sm"
            >
              {{ taxYear.year }}
            </span>
          </CollapsibleContent>
        </Collapsible>

        <!-- Stock Link -->
        <RouterLink
          to="/stocks"
          :class="[
            'item',
            isCurrentPath('/stocks') ? 'background-color:#000 border-l-2 border-l-gray-500' : '',
            !isFamilySelected ? 'opacity-50 cursor-not-allowed pointer-events-none' : '',
          ]"
          @click.prevent="
            () => {
              if (isFamilySelected) {
                $router.push('/stocks')
              }
            }
          "
        >
          Stocks
        </RouterLink>
      </div>
    </div>
  </nav>
</template>
