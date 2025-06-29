<script setup>
import { useProjectStore } from '@/stores/project'
import { RouterLink } from 'vue-router'
import axios from 'axios'
import { ref } from 'vue'

const projectStore = useProjectStore()

const taxStatements = ref([])

projectStore.$subscribe(async (MutationObserver, state) => {
  try {
    const url = `http://localhost:5001/api/projects/${state.projectId}`
    const response = await axios.get(url)
    taxStatements.value = []
    for (const t of response.data) {
      taxStatements.value.push(t)
    }
  } catch (error) {
    console.error('Error fetching tax statements:', error)
  }
})
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
