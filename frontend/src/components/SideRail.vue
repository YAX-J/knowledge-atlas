<script setup lang="ts">
import { Connection, Collection, Document, Filter, QuestionFilled } from '@element-plus/icons-vue'

defineProps<{ active: string }>()
const emit = defineEmits<{ change: [value: string] }>()

const items = [
  { id: 'graph', label: '知识图谱', icon: Connection },
  { id: 'projects', label: '我的项目', icon: Collection },
  { id: 'sources', label: '资料来源', icon: Document },
  { id: 'questions', label: '问答记录', icon: QuestionFilled },
]
</script>

<template>
  <nav class="side-rail" aria-label="主要导航">
    <button
      v-for="item in items"
      :key="item.id"
      type="button"
      :class="{ active: active === item.id }"
      :aria-label="item.label"
      :aria-current="active === item.id ? 'page' : undefined"
      :title="item.label"
      @click="emit('change', item.id)"
    >
      <component :is="item.icon" />
      <span>{{ item.label }}</span>
    </button>
    <div class="rail-divider" />
    <button type="button" aria-label="筛选图谱" title="筛选图谱" @click="emit('change', 'filter')">
      <Filter />
      <span>筛选</span>
    </button>
  </nav>
</template>
