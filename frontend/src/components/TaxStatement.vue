<script setup>
defineProps({
  taxStatement: Object,
})

// Define the segments you want to display, with their keys and icons
const segments = [
  {
    key: 'income_segment',
    label: 'Income',
    icon: 'pi-briefcase',
    items: {
      salary_1_1AJ: { label: 'Salary 1st contributor', box_id: '1AJ' },
      salary_2_1BJ: { label: 'Salary 2nd contributor', box_id: '1BJ' },
    },
  },
  {
    key: 'charity_segment',
    label: 'Charity',
    icon: 'pi-gift',
    items: {
      charity_donation_7UD: { label: 'Charity (people in difficulty)', box_id: '7UD' },
      charity_donation_7UF: { label: 'Charity (general)', box_id: '7UF' },
    },
  },
  {
    key: 'retirement_segment',
    label: 'Retirement Investment',
    icon: 'pi-car',
    items: {
      fixed_income_interests_2TR: {
        label: 'Interests received from fixed income investment',
        box_id: '2TR',
      },
      fixed_income_interests_already_taxed_2BH: {
        label: 'Interests from fixed income already taxed',
        box_id: '2BH',
      },
      interest_tax_already_paid_2CK: {
        label: 'Tax on fixed income interests already paid',
        box_id: '2CK',
      },
    },
  },
  {
    key: 'service_segment',
    label: 'Service Charges',
    icon: 'pi-bolt',
    items: {
      children_daycare_fees_7GA: { label: 'Children daycare fees', box_id: '7GA' },
    },
  },
  {
    key: 'fixed_income_segment',
    label: 'Fixed Income Investment',
    icon: 'pi-euro',
    items: {
      fixed_income_interests_2TR: {
        label: 'Interests received from fixed income investment',
        box_id: '2TR',
      },
      fixed_income_interests_already_taxed_2BH: {
        label: 'Interests from fixed income already taxed',
        box_id: '2BH',
      },
      interest_tax_already_paid_2CK: {
        label: 'Tax on fixed income interests already paid',
        box_id: '2CK',
      },
    },
  },
  { key: 'other_investment_segment', label: 'Other Investments', icon: 'pi-wallet', items: {} },
  {
    key: 'shareholding_segment',
    label: 'Shareholding',
    icon: 'pi-chart-line',
    items: {
      acquisition_gain_50p_rebates_1WZ: {
        label: 'Acquisition gain 50% rebates',
        box_id: '1WZ',
      },
      acquisition_gain_rebates_1UZ: { label: 'Acquisition gain rebates', box_id: '1UZ' },
      capital_gain_3VG: { label: 'Capital gain', box_id: '3VG' },
      capital_loss_3VH: { label: 'Capital loss', box_id: '3VH' },
      exercise_gain_1_1TT: { label: 'Exercise gain 1st contributor', box_id: '1TT' },
      exercise_gain_2_1UT: { label: 'Exercise gain 2nd contributor', box_id: '1UT' },
      taxable_acquisition_gain_1TZ: { label: 'Taxable acquisition gain', box_id: '1TZ' },
    },
  },
]
</script>

<template>
  <div class="mr-5">
    <div class="text-2xl text-center mb-2">Statement</div>
    <table class="table-fixed rounded-lg shadow bg-white">
      <tbody>
        <template v-for="segment in segments" :key="segment.key">
          <template v-if="taxStatement[segment.key]">
            <tr v-for="(val, field, idx) in taxStatement[segment.key]" :key="idx">
              <td
                v-if="idx === 0"
                :rowspan="Object.keys(taxStatement[segment.key]).length"
                class="bg-gray-100 py-2 px-4 border-y border-gray-400"
              >
                <div class="font-semibold text-lg flex items-center align-center">
                  <i :class="`pi ${segment.icon} mr-2 text-xl`"></i>
                  {{ segment.label }}
                </div>
              </td>
              <td class="bg-gray-50 px-4 py-2 border-y border-gray-300">
                {{ segment.items[field].label }}
              </td>
              <td class="bg-gray-50 px-4 py-2 border-y border-gray-300 border-l">
                <span class="font-light text-gray-500">{{ segment.items[field].box_id }}</span>
              </td>
              <td class="px-4 py-2 border-y border-gray-200 text-right">
                {{ val.toLocaleString() }} €
              </td>
            </tr>
          </template>
        </template>
      </tbody>
    </table>
  </div>
</template>
