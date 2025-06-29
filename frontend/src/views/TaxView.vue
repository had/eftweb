<script setup>
import { onMounted, ref } from 'vue'
import axios from 'axios'
import { useRoute } from 'vue-router'

const taxStatement = ref({})
const taxEstimation = ref({})
const loading = ref(true)

onMounted(async () => {
  try {
    const route = useRoute()
    const taxId = route.params.taxId
    const [response_statement, response_taxsim] = await axios.all([
      axios.get(`http://localhost:5001/api/taxes/${taxId}`),
      axios.get(`http://localhost:5001/api/taxes/${taxId}/estimation`),
    ])
    taxStatement.value = response_statement.data
    taxEstimation.value = response_taxsim.data
    loading.value = false
  } catch (error) {
    console.error('Error fetching tax statement:', error)
  }
})
</script>

<template>
  <div class="flex-col ml-8">
    <h1 class="logo px-3 py-5 mx-auto my-3">Tax for year {{ taxStatement.year }}</h1>
    <div v-if="loading">
      <ProgressSpinner />
    </div>
    <section v-else class="flex mx-5">
      <TaxStatement :taxStatement="taxStatement" />
      <TaxEstimation :taxEstimation="taxEstimation" />
    </section>
  </div>
  <!-- {{ taxStatement }} -->
</template>
