<script setup lang="ts">
import { Connection, Collection, Document, Filter, QuestionFilled } from '@element-plus/icons-vue'

defineProps<{ active: string }>()
const emit = defineEmits<{ change: [value: string] }>()

const items = [
  { id: 'workbench', label: '工作台', icon: Collection },
  { id: 'sources', label: '资料与审核', icon: Document },
  { id: 'graph', label: '知识图谱', icon: Connection },
  { id: 'conversations', label: '证据会话', icon: QuestionFilled },
  { id: 'agents', label: '协作任务', icon: Connection },
  { id: 'projects', label: '我的项目', icon: Collection },
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
