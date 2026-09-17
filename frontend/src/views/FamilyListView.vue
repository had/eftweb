<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { Pencil, Plus, Trash2 } from 'lucide-vue-next'
import { useFamilyStore } from '@/stores/family'
import FamilyFormModal from '@/components/FamilyFormModal.vue'
import DeleteConfirmModal from '@/components/DeleteConfirmModal.vue'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

const router = useRouter()
const familyStore = useFamilyStore()
const families = ref([])
const loading = ref(true)
const error = ref('')
const showArchived = ref(false)
const showForm = ref(false)
const editingFamily = ref(null)
const archivingFamily = ref(null)
const showArchiveConfirm = ref(false)

const loadFamilies = async () => {
  loading.value = true
  error.value = ''
  try {
    const response = await axios.get('/api/families', { params: { archived: showArchived.value } })
    families.value = response.data
  } catch (requestError) {
    error.value = 'Failed to load families. Please try again.'
  } finally {
    loading.value = false
  }
}

onMounted(loadFamilies)

const selectFamily = (family) => {
  familyStore.setCurrentFamily(family)
  router.push('/family')
}

const openCreate = () => { editingFamily.value = null; showForm.value = true }
const openEdit = (family) => { editingFamily.value = family; showForm.value = true }
const formSaved = loadFamilies
const openArchive = (family) => { archivingFamily.value = family; showArchiveConfirm.value = true }

const archiveFamily = async () => {
  if (!archivingFamily.value) return
  await axios.delete(`/api/families/${archivingFamily.value.id}`)
  if (familyStore.familyId === archivingFamily.value.id) familyStore.clearCurrentFamily()
  showArchiveConfirm.value = false
  archivingFamily.value = null
  await loadFamilies()
}

const familyName = (family) => `${family.taxpayer1.first_name} ${family.taxpayer1.last_name}`
</script>

<template>
  <div class="p-8">
    <div class="mb-8 flex items-start justify-between gap-4"><div><h1 class="text-3xl font-bold mb-2">{{ showArchived ? 'Archived Families' : 'Select a Family' }}</h1><p class="text-muted-foreground">{{ showArchived ? 'Families archived from the active list.' : 'Choose a family to view its tax returns and stock portfolio.' }}</p></div><Button variant="outline" @click="showArchived = !showArchived; loadFamilies()">{{ showArchived ? 'Show Active Families' : 'Show Archived Families' }}</Button></div>
    <div v-if="loading" class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3"><Card v-for="index in 3" :key="index" class="h-48 animate-pulse" /></div>
    <div v-else-if="error" class="text-center py-12"><p class="text-destructive text-lg">{{ error }}</p><Button class="mt-4" @click="loadFamilies">Retry</Button></div>
    <div v-else class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
      <Card v-if="!showArchived" class="cursor-pointer border-2 border-dashed p-6 transition-shadow hover:shadow-lg" @click="openCreate"><div class="flex h-48 flex-col items-center justify-center gap-3"><Plus class="h-8 w-8 text-muted-foreground" /><div class="text-lg font-semibold">Add a New Family</div></div></Card>
      <Card v-for="family in families" :key="family.id" :class="['relative p-6', !showArchived && 'cursor-pointer transition-shadow hover:shadow-lg']" @click="!showArchived && selectFamily(family)">
        <div v-if="!showArchived" class="absolute right-3 top-3 flex gap-1"><Button variant="ghost" size="icon" @click.stop="openEdit(family)"><Pencil class="h-4 w-4" /></Button><Button variant="ghost" size="icon" class="text-destructive" @click.stop="openArchive(family)"><Trash2 class="h-4 w-4" /></Button></div>
        <div class="flex h-48 flex-col gap-3"><div class="text-xl font-bold pr-12">{{ familyName(family) }}</div><div class="text-sm text-muted-foreground">{{ family.taxpayer2 ? 'Two taxpayers' : 'One taxpayer' }}</div><div class="text-sm text-muted-foreground">{{ family.children.length }} {{ family.children.length === 1 ? 'child' : 'children' }}</div><div class="flex-1" /><Button v-if="!showArchived" variant="outline" class="w-full" @click.stop="selectFamily(family)">Select →</Button></div>
      </Card>
      <p v-if="families.length === 0" class="text-muted-foreground">No {{ showArchived ? 'archived' : 'active' }} families found.</p>
    </div>
    <FamilyFormModal v-model:open="showForm" :family="editingFamily" @saved="formSaved" />
    <DeleteConfirmModal v-model:open="showArchiveConfirm" :family-name="archivingFamily ? familyName(archivingFamily) : ''" @confirm="archiveFamily" @cancel="showArchiveConfirm = false" />
  </div>
</template>
