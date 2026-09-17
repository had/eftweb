<script setup>
import { ref, watch } from 'vue'
import axios from 'axios'
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'

const props = defineProps({ open: Boolean, family: Object })
const emit = defineEmits(['update:open', 'saved'])

const emptyMember = () => ({ first_name: '', last_name: '', day: '', month: '', year: '' })
const formMember = (member) => {
  const [year = '', month = '', day = ''] = member?.date_of_birth?.split('-') || []
  return { first_name: member?.first_name || '', last_name: member?.last_name || '', day, month, year }
}
const memberPayload = (member) => ({
  first_name: member.first_name.trim(),
  last_name: member.last_name.trim(),
  date_of_birth: `${member.year.padStart(4, '0')}-${member.month.padStart(2, '0')}-${member.day.padStart(2, '0')}`,
})
const taxpayer1 = ref(emptyMember())
const taxpayer2 = ref(emptyMember())
const showTaxpayer2 = ref(false)
const children = ref([])
const error = ref('')
const loading = ref(false)

watch(
  () => props.family,
  (family) => {
    taxpayer1.value = formMember(family?.taxpayer1)
    taxpayer2.value = formMember(family?.taxpayer2)
    showTaxpayer2.value = Boolean(family?.taxpayer2)
    children.value = family?.children?.map(formMember) || []
    error.value = ''
  },
  { immediate: true },
)

const memberError = (member, label) => {
  if (!member.first_name.trim() || !member.last_name.trim() || !member.day || !member.month || !member.year) {
    return `Complete the first name, last name, and date of birth for ${label}.`
  }
  const day = Number(member.day)
  const month = Number(member.month)
  const year = Number(member.year)
  const date = new Date(Date.UTC(year, month - 1, day))
  if (
    !Number.isInteger(day) || !Number.isInteger(month) || !Number.isInteger(year) ||
    year < 1 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day
  ) {
    return `Enter a valid date of birth for ${label}.`
  }
  return ''
}

const addChild = () => {
  if (children.value.length < 6) children.value.push(emptyMember())
}

const removeChild = (index) => children.value.splice(index, 1)

const close = () => {
  if (!loading.value) {
    emit('update:open', false)
    error.value = ''
  }
}

const submit = async () => {
  error.value = ''
  const members = [
    [taxpayer1.value, 'taxpayer 1'],
    ...(showTaxpayer2.value ? [[taxpayer2.value, 'taxpayer 2']] : []),
    ...children.value.map((child, index) => [child, `child ${index + 1}`]),
  ]
  error.value = members.map(([member, label]) => memberError(member, label)).find(Boolean)
  if (error.value) return

  loading.value = true
  const payload = {
    taxpayer1: memberPayload(taxpayer1.value),
    taxpayer2: showTaxpayer2.value ? memberPayload(taxpayer2.value) : null,
    children: children.value.map(memberPayload),
  }
  try {
    if (props.family) {
      await axios.put(`/api/families/${props.family.id}`, payload)
    } else {
      await axios.post('/api/families', payload)
    }
    emit('saved')
    emit('update:open', false)
  } catch (requestError) {
    error.value = requestError.response?.data?.error || 'Failed to save family. Please try again.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Dialog :open="open" @update:open="close">
    <DialogContent class="max-h-[90vh] overflow-y-auto sm:max-w-[600px]">
      <DialogHeader>
        <DialogTitle>{{ family ? 'Edit Family' : 'Add a New Family' }}</DialogTitle>
      </DialogHeader>
      <form class="space-y-6 py-4" @submit.prevent="submit">
        <section class="space-y-3">
          <h3 class="font-semibold">Taxpayer 1</h3>
          <div class="grid gap-3 sm:grid-cols-2">
            <div class="space-y-1"><Label for="taxpayer1-first-name">First name *</Label><input id="taxpayer1-first-name" v-model="taxpayer1.first_name" class="h-9 w-full rounded-md border px-3 py-1" /></div>
            <div class="space-y-1"><Label for="taxpayer1-last-name">Last name *</Label><input id="taxpayer1-last-name" v-model="taxpayer1.last_name" class="h-9 w-full rounded-md border px-3 py-1" /></div>
          </div>
          <div class="space-y-1"><Label>Date of birth *</Label><div class="grid grid-cols-3 gap-2"><input v-model="taxpayer1.day" class="h-9 rounded-md border px-3 py-1" inputmode="numeric" placeholder="DD" /><input v-model="taxpayer1.month" class="h-9 rounded-md border px-3 py-1" inputmode="numeric" placeholder="MM" /><input v-model="taxpayer1.year" class="h-9 rounded-md border px-3 py-1" inputmode="numeric" placeholder="YYYY" /></div></div>
        </section>

        <section class="space-y-3 border-t pt-4">
          <label class="flex items-center gap-2 font-semibold"><input v-model="showTaxpayer2" type="checkbox" /> Include taxpayer 2</label>
          <template v-if="showTaxpayer2">
          <div class="grid gap-3 sm:grid-cols-2">
            <div class="space-y-1"><Label for="taxpayer2-first-name">First name *</Label><input id="taxpayer2-first-name" v-model="taxpayer2.first_name" class="h-9 w-full rounded-md border px-3 py-1" /></div>
            <div class="space-y-1"><Label for="taxpayer2-last-name">Last name *</Label><input id="taxpayer2-last-name" v-model="taxpayer2.last_name" class="h-9 w-full rounded-md border px-3 py-1" /></div>
          </div>
          <div class="space-y-1"><Label>Date of birth *</Label><div class="grid grid-cols-3 gap-2"><input v-model="taxpayer2.day" class="h-9 rounded-md border px-3 py-1" inputmode="numeric" placeholder="DD" /><input v-model="taxpayer2.month" class="h-9 rounded-md border px-3 py-1" inputmode="numeric" placeholder="MM" /><input v-model="taxpayer2.year" class="h-9 rounded-md border px-3 py-1" inputmode="numeric" placeholder="YYYY" /></div></div>
          </template>
        </section>

        <section class="space-y-3 border-t pt-4">
          <div class="flex items-center justify-between"><h3 class="font-semibold">Children</h3><Button type="button" variant="outline" :disabled="children.length === 6" @click="addChild">Add child</Button></div>
          <div v-for="(child, index) in children" :key="index" class="space-y-3 rounded-md border p-3">
            <div class="flex justify-between"><span class="font-medium">Child {{ index + 1 }}</span><Button type="button" variant="ghost" @click="removeChild(index)">Remove</Button></div>
            <div class="grid gap-3 sm:grid-cols-2">
              <div class="space-y-1"><Label :for="`child-${index}-first-name`">First name *</Label><input :id="`child-${index}-first-name`" v-model="child.first_name" class="h-9 w-full rounded-md border px-3 py-1" /></div>
              <div class="space-y-1"><Label :for="`child-${index}-last-name`">Last name *</Label><input :id="`child-${index}-last-name`" v-model="child.last_name" class="h-9 w-full rounded-md border px-3 py-1" /></div>
            </div>
            <div class="space-y-1"><Label>Date of birth *</Label><div class="grid grid-cols-3 gap-2"><input v-model="child.day" class="h-9 rounded-md border px-3 py-1" inputmode="numeric" placeholder="DD" /><input v-model="child.month" class="h-9 rounded-md border px-3 py-1" inputmode="numeric" placeholder="MM" /><input v-model="child.year" class="h-9 rounded-md border px-3 py-1" inputmode="numeric" placeholder="YYYY" /></div></div>
          </div>
        </section>
        <p v-if="error" class="text-sm text-destructive">{{ error }}</p>
      </form>
      <DialogFooter><Button type="button" variant="outline" :disabled="loading" @click="close">Cancel</Button><Button :disabled="loading" @click="submit">{{ loading ? 'Saving...' : family ? 'Update Family' : 'Add Family' }}</Button></DialogFooter>
    </DialogContent>
  </Dialog>
</template>
