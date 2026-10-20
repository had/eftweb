<script setup>
import { ref, watch } from 'vue'
import axios from 'axios'
import { Pencil, Plus, Trash2 } from 'lucide-vue-next'
import { useFamilyStore } from '@/stores/family'
import EftLayout from '@/components/EftLayout.vue'
import StockFormModal from '@/components/StockFormModal.vue'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

const familyStore = useFamilyStore()
const stocks = ref([])
const showArchived = ref(false)
const loading = ref(false)
const error = ref('')
const stocksVersion = ref(0)
const showForm = ref(false)
const editingStock = ref(null)
const archivingStock = ref(null)
const archiving = ref(false)
const archiveError = ref('')

watch(
  () => familyStore.familyId,
  () => {
    showForm.value = false
    editingStock.value = null
    archivingStock.value = null
    archiveError.value = ''
  },
)

watch(
  [() => familyStore.familyId, showArchived, stocksVersion],
  async ([familyId], _, onCleanup) => {
    let current = true
    onCleanup(() => {
      current = false
    })
    stocks.value = []
    error.value = ''
    loading.value = Boolean(familyId)
    if (!familyId) return
    try {
      const response = await axios.get(`/api/families/${familyId}/stocks`, {
        params: { archived: showArchived.value },
      })
      if (current) stocks.value = response.data
    } catch (requestError) {
      if (current)
        error.value =
          requestError.response?.data?.error || 'Failed to load stocks. Please try again.'
    } finally {
      if (current) loading.value = false
    }
  },
  { immediate: true },
)

const reload = () => {
  stocksVersion.value += 1
}
const openCreate = () => {
  editingStock.value = null
  showForm.value = true
}
const openEdit = (stock) => {
  editingStock.value = stock
  showForm.value = true
}
const stockSaved = () => {
  showArchived.value = false
  reload()
}
const openArchive = (stock) => {
  archiveError.value = ''
  archivingStock.value = stock
}
const closeArchive = () => {
  if (!archiving.value) archivingStock.value = null
}
const archiveStock = async () => {
  if (!archivingStock.value || archiving.value) return
  const familyId = familyStore.familyId
  archiving.value = true
  archiveError.value = ''
  try {
    await axios.delete(`/api/stocks/${archivingStock.value.id}`)
    if (familyId === familyStore.familyId) {
      archivingStock.value = null
      reload()
    }
  } catch (requestError) {
    if (familyId === familyStore.familyId) {
      archiveError.value =
        requestError.response?.data?.error || 'Failed to archive the stock. Please try again.'
    }
  } finally {
    archiving.value = false
  }
}
</script>

<template>
  <EftLayout :title="familyStore.familyName || 'Family'">
    <div class="mb-6 flex items-center justify-between gap-4">
      <h2 class="text-2xl font-semibold">{{ showArchived ? 'Archived Stocks' : 'Stocks' }}</h2>
      <Button v-if="familyStore.familyId" variant="outline" @click="showArchived = !showArchived">
        {{ showArchived ? 'Show Active' : 'Show Archived' }}
      </Button>
    </div>
    <p v-if="!familyStore.familyId" class="text-muted-foreground">
      Select a family to manage stocks.
    </p>
    <div
      v-else-if="loading"
      class="grid gap-3 sm:grid-cols-2"
      role="status"
      aria-label="Loading stocks"
    >
      <div v-for="index in 2" :key="index" class="h-28 animate-pulse rounded-lg bg-muted" />
    </div>
    <div v-else-if="error" class="py-4">
      <p role="alert" class="text-destructive">{{ error }}</p>
      <Button class="mt-4" variant="outline" @click="reload">Retry</Button>
    </div>
    <section v-else class="grid gap-3 sm:grid-cols-2">
      <button
        v-if="!showArchived"
        type="button"
        class="cursor-pointer rounded-xl border-2 border-dashed text-card-foreground transition-shadow hover:shadow-lg focus-visible:outline-2 focus-visible:outline-ring"
        @click="openCreate"
      >
        <span class="flex min-h-28 flex-col items-center justify-center gap-2 p-4 text-center">
          <Plus class="h-6 w-6 text-muted-foreground" />
          <span class="font-medium">Add a New Stock</span>
        </span>
      </button>
      <Card v-for="stock in stocks" :key="stock.id" class="relative">
        <CardContent
          class="flex min-h-28 flex-col items-start justify-center gap-2 p-4"
          :class="!showArchived && 'pr-24'"
        >
          <div v-if="!showArchived" class="absolute right-2 top-2 flex gap-1">
            <Button
              variant="ghost"
              size="icon"
              :aria-label="`Edit ${stock.name}`"
              @click.stop="openEdit(stock)"
              ><Pencil class="h-4 w-4"
            /></Button>
            <Button
              variant="ghost"
              size="icon"
              class="text-destructive"
              :aria-label="`Archive ${stock.name}`"
              @click.stop="openArchive(stock)"
              ><Trash2 class="h-4 w-4"
            /></Button>
          </div>
          <span class="max-w-full break-words text-lg font-medium">{{ stock.name }}</span>
          <span class="rounded bg-muted px-2 py-0.5 text-xs">{{ stock.symbol }}</span>
        </CardContent>
      </Card>
      <p v-if="stocks.length === 0" class="text-sm text-muted-foreground sm:col-span-2">
        No {{ showArchived ? 'archived' : 'active' }} stocks found.
      </p>
    </section>
    <StockFormModal
      :key="familyStore.familyId"
      v-model:open="showForm"
      :family-id="familyStore.familyId"
      :stock="editingStock"
      @saved="stockSaved"
    />
    <Dialog :open="Boolean(archivingStock)" @update:open="closeArchive">
      <DialogContent class="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Archive Stock</DialogTitle>
          <DialogDescription>
            Are you sure you want to archive {{ archivingStock?.name }} ({{
              archivingStock?.symbol
            }})? It will be hidden from the active list.
          </DialogDescription>
        </DialogHeader>
        <p v-if="archiveError" role="alert" class="text-sm text-destructive">{{ archiveError }}</p>
        <DialogFooter>
          <Button variant="outline" :disabled="archiving" @click="closeArchive">Cancel</Button>
          <Button variant="destructive" :disabled="archiving" @click="archiveStock">{{
            archiving ? 'Archiving...' : 'Archive'
          }}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </EftLayout>
</template>
