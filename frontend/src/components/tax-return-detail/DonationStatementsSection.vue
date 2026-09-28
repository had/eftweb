<script setup>
import { Pencil, Trash2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const props = defineProps({
  statements: {
    type: Array,
    required: true,
  },
  donationTypes: {
    type: Array,
    required: true,
  },
})

defineEmits(['add', 'edit', 'delete'])

const donationTypeFor = (statement) =>
  props.donationTypes.find((type) => type.code === statement.donation_type)
const formatAmount = (amount) =>
  new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'EUR' }).format(Number(amount))
</script>

<template>
  <Card class="w-full">
    <CardHeader class="flex flex-row items-center justify-between gap-4">
      <CardTitle>Donation statements</CardTitle>
      <Button @click="$emit('add')">Add donation statement</Button>
    </CardHeader>
    <CardContent>
      <div v-if="statements.length === 0" class="text-sm text-muted-foreground">
        No donation statements added yet.
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full border-collapse text-left text-sm">
          <thead>
            <tr class="border-b">
              <th class="p-3 font-medium">Name</th>
              <th class="p-3 font-medium">Type</th>
              <th class="p-3 font-medium">Amount</th>
              <th class="p-3 font-medium">Tax reduction / box</th>
              <th class="p-3"><span class="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="statement in statements" :key="statement.id" class="border-b last:border-0">
              <td class="p-3">{{ statement.name }}</td>
              <td class="p-3">
                {{ donationTypeFor(statement)?.label || statement.donation_type }}
              </td>
              <td class="p-3 whitespace-nowrap">{{ formatAmount(statement.amount) }}</td>
              <td class="p-3 text-muted-foreground">
                {{ donationTypeFor(statement)?.tax_reduction }} ·
                {{ donationTypeFor(statement)?.tax_return_box }}
              </td>
              <td class="p-3">
                <span class="flex justify-end gap-1"
                  ><Button
                    variant="ghost"
                    size="icon"
                    aria-label="Edit donation statement"
                    @click="$emit('edit', statement)"
                    ><Pencil class="h-4 w-4" /></Button
                  ><Button
                    variant="ghost"
                    size="icon"
                    class="text-destructive"
                    aria-label="Delete donation statement"
                    @click="$emit('delete', statement)"
                    ><Trash2 class="h-4 w-4" /></Button
                ></span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </CardContent>
  </Card>
</template>
