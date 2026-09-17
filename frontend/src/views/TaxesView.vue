<script setup>
import { useProjectStore } from '@/stores/project'
import { RouterLink } from 'vue-router'
import axios from 'axios'
import { ref, watch } from 'vue'

const projectStore = useProjectStore()

const taxStatements = ref([])

watch(
  [() => projectStore.projectId, () => projectStore.taxStatementsVersion],
  async ([projectId]) => {
    if (!projectId) {
      taxStatements.value = []
      return
    }

    try {
      const response = await axios.get(`/api/projects/${projectId}/tax-statements`)
      taxStatements.value = response.data
    } catch (error) {
      console.error('Error fetching tax statements:', error)
      taxStatements.value = []
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="flex-col ml-8">
    <h1 class="logo px-3 py-5 mx-auto my-3">Taxes</h1>
    <section>
      <ul class="flex flex-col">
        <li v-for="taxStatement in taxStatements" :key="taxStatement.id" class="p-2">
          <RouterLink
            :to="{
              name: 'tax',
              params: { taxId: taxStatement.id },
            }"
            >{{ taxStatement.year }}</RouterLink
          >
        </li>
      </ul>
    </section>
  </div>
</template>
