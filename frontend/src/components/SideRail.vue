<script setup lang="ts">
import { computed } from 'vue'
import { deckGroups } from '../deckNavigation'

const props = defineProps<{ active: string; focusOnly?: boolean; counts?: Record<string, number | undefined> }>()
const emit = defineEmits<{ change: [value: string] }>()
const groups = computed(() => props.focusOnly ? deckGroups.filter(group => group.id === 'explore') : deckGroups)
</script>

<template>
  <nav class="side-rail" aria-label="主要导航">
    <button type="button" class="rail-brand" aria-label="Knowledge Atlas 图谱首页" title="返回图谱" @click="emit('change', 'graph')">KA</button>
    <div v-for="group in groups" :key="group.label" class="rail-group" role="group" :aria-label="group.label">
      <div class="rail-caption" aria-hidden="true">{{ group.label }}</div>
      <button v-for="item in group.items" :key="item.id" class="rail-button"
        type="button" :aria-label="item.label" :title="item.label"
        :aria-current="active === item.id ? 'page' : undefined"
        @click="emit('change', item.id)">
        <component :is="item.icon" aria-hidden="true" />
        <span v-if="counts?.[item.id] !== undefined" class="rail-badge" aria-hidden="true">{{ counts?.[item.id] }}</span>
      </button>
    </div>
  </nav>
</template>
