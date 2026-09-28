<script setup>
import { computed } from 'vue'
import { Pencil, Trash2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const props = defineProps({
  family: {
    type: Object,
    required: true,
  },
  statements: {
    type: Array,
    required: true,
  },
})

defineEmits(['add', 'edit', 'delete'])

const rows = computed(() => {
  const taxpayer1 = props.statements.filter((statement) => statement.taxpayer_role === 'taxpayer1')
  const taxpayer2 = props.statements.filter((statement) => statement.taxpayer_role === 'taxpayer2')

  return Array.from({ length: Math.max(taxpayer1.length, taxpayer2.length) }, (_, index) => ({
    taxpayer1: taxpayer1[index],
    taxpayer2: taxpayer2[index],
  }))
})
</script>

<template>
  <Card class="w-full">
    <CardHeader class="flex flex-row items-center justify-between gap-4">
      <CardTitle>Income statements</CardTitle>
      <Button @click="$emit('add')">Add income statement</Button>
    </CardHeader>
    <CardContent>
      <div v-if="rows.length === 0" class="text-sm text-muted-foreground">
        No income statements added yet.
      </div>
      <div v-else class="overflow-x-auto">
        <table class="w-full border-collapse text-left text-sm">
          <thead>
            <tr class="border-b">
              <th class="p-3 font-medium">
                {{ family.taxpayer1.first_name }} {{ family.taxpayer1.last_name }}
                <span class="text-xs font-normal text-muted-foreground">taxpayer 1</span>
              </th>
              <th v-if="family.taxpayer2" class="p-3 font-medium">
                {{ family.taxpayer2.first_name }} {{ family.taxpayer2.last_name }}
                <span class="text-xs font-normal text-muted-foreground">taxpayer 2</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in rows" :key="index" class="border-b last:border-0">
              <td class="p-3">
                <div v-if="row.taxpayer1" class="flex items-center justify-between gap-2">
                  <span>{{ row.taxpayer1.employer_name }}</span>
                  <span class="flex shrink-0 gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Edit income statement"
                      @click="$emit('edit', row.taxpayer1)"
                      ><Pencil class="h-4 w-4"
                    /></Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="text-destructive"
                      aria-label="Delete income statement"
                      @click="$emit('delete', row.taxpayer1)"
                      ><Trash2 class="h-4 w-4"
                    /></Button>
                  </span>
                </div>
              </td>
              <td v-if="family.taxpayer2" class="p-3">
                <div v-if="row.taxpayer2" class="flex items-center justify-between gap-2">
                  <span>{{ row.taxpayer2.employer_name }}</span>
                  <span class="flex shrink-0 gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Edit income statement"
                      @click="$emit('edit', row.taxpayer2)"
                      ><Pencil class="h-4 w-4"
                    /></Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      class="text-destructive"
                      aria-label="Delete income statement"
                      @click="$emit('delete', row.taxpayer2)"
                      ><Trash2 class="h-4 w-4"
                    /></Button>
                  </span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </CardContent>
  </Card>
</template>
