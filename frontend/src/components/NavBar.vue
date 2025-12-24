<script setup>
import { ref, watch, computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useProjectStore } from '@/stores/project'
import { Separator } from '@/components/ui/separator'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { ChevronDown, ChevronRight } from 'lucide-vue-next'
import axios from 'axios'

const route = useRoute()
const projectStore = useProjectStore()
const taxYears = ref([])
const isTaxExpanded = ref(false)

const isProjectSelected = computed(() => !!projectStore.projectId)

const isCurrentPath = (viewPath) => {
  return route.path === viewPath
}

// Watch for project changes and fetch tax years
watch(
  () => projectStore.projectId,
  async (newId) => {
    if (newId) {
      try {
        const response = await axios.get(`/api/projects/${newId}`)
        taxYears.value = response.data.taxstatements
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
      <!-- Title -->
      <RouterLink to="/" class="logo py-4 self-center">Easy French Tax</RouterLink>

      <!-- Separator -->
      <Separator class="my-2 mx-2" />

      <!-- Project Section -->
      <div class="px-3 py-2">
        <RouterLink
          v-if="!isProjectSelected"
          to="/projects"
          class="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          Select a project →
        </RouterLink>
        <div v-else class="text-sm font-medium truncate" :title="projectStore.projectName">
          {{ projectStore.projectName }}
        </div>
      </div>

      <!-- Separator -->
      <Separator class="my-2 mx-2" />

      <!-- Navigation Links -->
      <div class="flex flex-col mt-2">
        <!-- Tax Link (Collapsible) -->
        <Collapsible v-model:open="isTaxExpanded">
          <CollapsibleTrigger
            :class="[
              'item flex items-center justify-between w-full',
              isCurrentPath('/taxes') ? 'background-color:#000 border-l-2 border-l-gray-500' : '',
              !isProjectSelected ? 'opacity-50 cursor-not-allowed' : '',
            ]"
            :disabled="!isProjectSelected"
            @click.prevent="
              () => {
                if (!isProjectSelected) return
                if (taxYears.length > 0) {
                  isTaxExpanded = !isTaxExpanded
                } else {
                  $router.push('/taxes')
                }
              }
            "
          >
            <span>Taxes</span>
            <component
              :is="isTaxExpanded ? ChevronDown : ChevronRight"
              v-if="isProjectSelected && taxYears.length > 0"
              class="h-4 w-4"
            />
          </CollapsibleTrigger>

          <CollapsibleContent v-if="isProjectSelected">
            <RouterLink
              v-for="taxYear in taxYears"
              :key="taxYear.id"
              :to="`/taxes/${taxYear.id}`"
              :class="[
                'item pl-8 text-sm',
                isCurrentPath(`/taxes/${taxYear.id}`)
                  ? 'background-color:#000 border-l-2 border-l-gray-500'
                  : '',
              ]"
            >
              {{ taxYear.year }}
            </RouterLink>
          </CollapsibleContent>
        </Collapsible>

        <!-- Stock Link -->
        <RouterLink
          to="/stocks"
          :class="[
            'item',
            isCurrentPath('/stocks') ? 'background-color:#000 border-l-2 border-l-gray-500' : '',
            !isProjectSelected ? 'opacity-50 cursor-not-allowed pointer-events-none' : '',
          ]"
          @click.prevent="
            () => {
              if (isProjectSelected) {
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
