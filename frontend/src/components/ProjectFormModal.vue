<script setup>
import { ref, watch } from 'vue'
import axios from 'axios'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

const props = defineProps({
  open: Boolean,
  project: Object,
})

const emit = defineEmits(['update:open', 'saved'])

const formData = ref({
  name: '',
  married: false,
  nb_children: 0,
})

const errors = ref({})
const loading = ref(false)

watch(
  () => props.project,
  (newProject) => {
    if (newProject) {
      formData.value = {
        name: newProject.name || '',
        married: newProject.married || false,
        nb_children: newProject.nb_children || 0,
      }
    } else {
      formData.value = {
        name: '',
        married: false,
        nb_children: 0,
      }
    }
  },
  { immediate: true },
)

const validateForm = () => {
  errors.value = {}

  if (!formData.value.name || formData.value.name.trim() === '') {
    errors.value.name = 'Project name is required'
    return false
  }

  if (formData.value.nb_children < 0) {
    errors.value.nb_children = 'Number of children cannot be negative'
    return false
  }

  return true
}

const handleSubmit = async () => {
  if (!validateForm()) return

  loading.value = true
  errors.value = {}

  try {
    if (props.project) {
      await axios.put(`/api/projects/${props.project.id}`, formData.value)
    } else {
      await axios.post('/api/projects', formData.value)
    }

    emit('saved')
    emit('update:open', false)
  } catch (error) {
    if (error.response?.status === 409) {
      errors.value.name = 'Project name already exists'
    } else if (error.response?.data?.error) {
      errors.value.general = error.response.data.error
    } else {
      errors.value.general = 'Failed to save project. Please try again.'
    }
  } finally {
    loading.value = false
  }
}

const handleClose = () => {
  emit('update:open', false)
  errors.value = {}
}
</script>

<template>
  <Dialog :open="open" @update:open="handleClose">
    <DialogContent class="sm:max-w-[425px]">
      <DialogHeader>
        <DialogTitle>{{ project ? 'Edit Project' : 'Create New Project' }}</DialogTitle>
      </DialogHeader>

      <form @submit.prevent="handleSubmit" class="space-y-4 py-4">
        <div class="space-y-2">
          <Label for="name">Project Name *</Label>
          <Input
            id="name"
            v-model="formData.name"
            placeholder="My Tax Project"
            :class="{ 'border-destructive': errors.name }"
          />
          <p v-if="errors.name" class="text-sm text-destructive">{{ errors.name }}</p>
        </div>

        <div class="space-y-2">
          <Label>Marital Status *</Label>
          <RadioGroup v-model:model-value="formData.married">
            <div class="flex items-center space-x-2">
              <RadioGroupItem :value="false" id="single" />
              <Label for="single" class="font-normal cursor-pointer">Single</Label>
            </div>
            <div class="flex items-center space-x-2">
              <RadioGroupItem :value="true" id="married" />
              <Label for="married" class="font-normal cursor-pointer">Married</Label>
            </div>
          </RadioGroup>
        </div>

        <div class="space-y-2">
          <Label for="nb_children">Number of Children</Label>
          <Input
            id="nb_children"
            v-model.number="formData.nb_children"
            type="number"
            min="0"
            :class="{ 'border-destructive': errors.nb_children }"
          />
          <p v-if="errors.nb_children" class="text-sm text-destructive">
            {{ errors.nb_children }}
          </p>
        </div>

        <p v-if="errors.general" class="text-sm text-destructive">{{ errors.general }}</p>
      </form>

      <DialogFooter>
        <Button type="button" variant="outline" @click="handleClose" :disabled="loading">
          Cancel
        </Button>
        <Button @click="handleSubmit" :disabled="loading">
          {{ loading ? 'Saving...' : project ? 'Update' : 'Create' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
