<script setup>
import { formatCurrency } from '@/lib/numberFormat.js'
import { ref, watch } from 'vue'
import axios from 'axios'
import { House, Pencil, Plus, Trash2 } from 'lucide-vue-next'
import { useFamilyStore } from '@/stores/family'
import EftLayout from '@/components/EftLayout.vue'
import PropertyFormModal from '@/components/PropertyFormModal.vue'
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
const properties = ref([])
const loading = ref(false)
const error = ref('')
const version = ref(0)
const showForm = ref(false)
const editingProperty = ref(null)
const deletingProperty = ref(null)
const deleting = ref(false)
const deleteError = ref('')
const formatValue = (value) =>
  formatCurrency(value)

watch(
  () => familyStore.familyId,
  () => {
    showForm.value = false
    editingProperty.value = null
    deletingProperty.value = null
    deleteError.value = ''
  },
)
watch(
  [() => familyStore.familyId, version],
  async ([familyId], _, onCleanup) => {
    let current = true
    onCleanup(() => {
      current = false
    })
    properties.value = []
    error.value = ''
    loading.value = Boolean(familyId)
    if (!familyId) return
    try {
      const response = await axios.get(`/api/families/${familyId}/properties`)
      if (current) properties.value = response.data
    } catch (requestError) {
      if (current)
        error.value =
          requestError.response?.data?.error || 'Failed to load properties. Please try again.'
    } finally {
      if (current) loading.value = false
    }
  },
  { immediate: true },
)
const reload = () => {
  version.value += 1
}
const openCreate = () => {
  editingProperty.value = null
  showForm.value = true
}
const openEdit = (property) => {
  editingProperty.value = property
  showForm.value = true
}
const openDelete = (property) => {
  deleteError.value = ''
  deletingProperty.value = property
}
const closeDelete = () => {
  if (!deleting.value) deletingProperty.value = null
}
const deleteProperty = async () => {
  if (!deletingProperty.value || deleting.value) return
  const familyId = familyStore.familyId
  const target = deletingProperty.value
  deleting.value = true
  deleteError.value = ''
  try {
    await axios.delete(`/api/families/${familyId}/properties/${target.id}`)
    if (familyId === familyStore.familyId && deletingProperty.value === target) {
      deletingProperty.value = null
      reload()
    }
  } catch (requestError) {
    if (familyId === familyStore.familyId && deletingProperty.value === target) {
      deleteError.value =
        requestError.response?.data?.error || 'Failed to delete the property. Please try again.'
    }
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <EftLayout :title="familyStore.familyName || 'Family'">
    <h2 class="mb-6 text-2xl font-semibold">Real Estate</h2>
    <p v-if="!familyStore.familyId" class="text-muted-foreground">
      Select a family to manage properties.
    </p>
    <div
      v-else-if="loading"
      class="grid gap-3 sm:grid-cols-2"
      role="status"
      aria-label="Loading properties"
    >
      <div v-for="index in 2" :key="index" class="h-28 animate-pulse rounded-lg bg-muted" />
    </div>
    <div v-else-if="error" class="py-4">
      <p role="alert" class="text-destructive">{{ error }}</p>
      <Button class="mt-4" variant="outline" @click="reload">Retry</Button>
    </div>
    <section v-else class="grid gap-3 sm:grid-cols-2">
      <button
        type="button"
        class="cursor-pointer rounded-xl border-2 border-dashed text-card-foreground transition-shadow hover:shadow-lg focus-visible:outline-2 focus-visible:outline-ring"
        @click="openCreate"
      >
        <span class="flex min-h-28 flex-col items-center justify-center gap-2 p-4 text-center">
          <Plus class="h-6 w-6 text-muted-foreground" />
          <span class="font-medium">Add a New Property</span>
        </span>
      </button>
      <Card
        v-for="property in properties"
        :key="property.id"
        class="relative transition-shadow hover:shadow-lg"
      >
        <CardContent class="flex min-h-28 flex-col items-start justify-center gap-2 p-4 pr-24">
          <div class="absolute right-2 top-2 flex gap-1">
            <Button
              variant="ghost"
              size="icon"
              :aria-label="`Edit ${property.name}`"
              @click="openEdit(property)"
            >
              <Pencil class="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              class="text-destructive"
              :aria-label="`Delete ${property.name}`"
              @click="openDelete(property)"
            >
              <Trash2 class="h-4 w-4" />
            </Button>
          </div>
          <div class="flex max-w-full items-center gap-2">
            <span v-if="property.is_principal_home" class="shrink-0" title="Principal home">
              <House class="h-5 w-5 text-primary" aria-hidden="true" />
              <span class="sr-only">Principal home</span>
            </span>
            <span class="min-w-0 break-words text-lg font-medium">{{ property.name }}</span>
          </div>
          <span class="text-sm text-muted-foreground">{{
            formatValue(property.estimated_value)
          }}</span>
        </CardContent>
      </Card>
      <p v-if="properties.length === 0" class="text-sm text-muted-foreground sm:col-span-2">
        No properties found.
      </p>
    </section>
    <PropertyFormModal
      :key="familyStore.familyId"
      v-model:open="showForm"
      :family-id="familyStore.familyId"
      :property="editingProperty"
      :properties="properties"
      @saved="reload"
    />
    <Dialog :open="Boolean(deletingProperty)" @update:open="closeDelete">
      <DialogContent class="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Delete Property</DialogTitle>
          <DialogDescription
            >Permanently delete {{ deletingProperty?.name }}? This cannot be
            undone.</DialogDescription
          >
        </DialogHeader>
        <p v-if="deleteError" role="alert" class="text-sm text-destructive">{{ deleteError }}</p>
        <DialogFooter>
          <Button variant="outline" :disabled="deleting" @click="closeDelete">Cancel</Button>
          <Button variant="destructive" :disabled="deleting" @click="deleteProperty">{{
            deleting ? 'Deleting...' : 'Delete'
          }}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </EftLayout>
</template>
