<script setup>
defineProps({
  taxEstimation: Object,
})

const detail_elements = [
  { key: 'household_shares', label: 'Household shares', unit: '' },
  { key: 'reference_fiscal_income', label: 'Reference fiscal income', unit: '€' },
  { key: 'taxable_income', label: 'Taxable income', unit: '€' },
  { key: 'taxable_investment_income', label: 'Taxable investment income', unit: '€' },
  { key: 'total_net_income', label: 'Total net income', unit: '€' },
  { key: 'tax_before_reductions', label: 'Tax before reduction', unit: '€' },
  { key: 'net_social_taxes', label: 'Net social taxes', unit: '€' },
  { key: 'net_taxes', label: 'Net taxes', unit: '€' },
]
</script>

<template>
  <div class="ml-5">
    <div class="text-2xl text-center mb-1">Estimation</div>
    <ul class="list-disc">
      <li class="flex justify-between items-center rounded-full bg-amber-200 m-2">
        <span class="font-bold px-3">Total</span>
        <div class="rounded-full p-2 bg-amber-300">
          {{ taxEstimation.total_taxes.toLocaleString() }} €
        </div>
      </li>
      <li
        v-for="element in detail_elements"
        :key="element.key"
        class="flex justify-between items-center rounded-full bg-blue-100 m-2"
      >
        <span class="px-3">{{ element.label }}</span>
        <div class="rounded-full p-2 bg-blue-200">
          {{ taxEstimation.details[element.key].toLocaleString() }} {{ element.unit }}
        </div>
      </li>
    </ul>
    <!-- <div>{{ taxEstimation.details }}</div> -->
    <!-- {{ detail_elements }} -->
  </div>
</template>
