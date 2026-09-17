import { ref } from 'vue'
import { defineStore } from 'pinia'

const familyLocalStorageKey = 'current_family'

export const useFamilyStore = defineStore('family', () => {
  const familyName = ref('')
  const familyId = ref(0)
  const taxReturnsVersion = ref(0)

  const storedFamily = localStorage.getItem(familyLocalStorageKey)
  if (storedFamily) {
    const family = JSON.parse(storedFamily)
    familyName.value = family.name
    familyId.value = family.id
  }

  function setCurrentFamily(family) {
    familyName.value = `${family.taxpayer1.first_name} ${family.taxpayer1.last_name}`
    familyId.value = family.id
    localStorage.setItem(familyLocalStorageKey, JSON.stringify({ name: familyName.value, id: familyId.value }))
  }

  function clearCurrentFamily() {
    familyName.value = ''
    familyId.value = 0
    localStorage.removeItem(familyLocalStorageKey)
  }

  function refreshTaxReturns() {
    taxReturnsVersion.value += 1
  }

  return { familyName, familyId, taxReturnsVersion, setCurrentFamily, clearCurrentFamily, refreshTaxReturns }
})
