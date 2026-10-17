<script setup lang="ts">
import { computed, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import type { KnowledgeNode } from '../types'

const props = defineProps<{
  nodes: KnowledgeNode[]
  selectedId: string
  graphActive: boolean
}>()

const emit = defineEmits<{
  select: [id: string]
}>()

const query = ref('')
const isFocused = ref(false)

const results = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  if (!keyword) return []
  return props.nodes.filter((node) =>
    `${node.label} ${node.description} ${node.project}`.toLowerCase().includes(keyword),
  ).slice(0, 5)
})

function choose(node: KnowledgeNode) {
  query.value = node.label
  isFocused.value = false
  emit('select', node.id)
}

function submit() {
  if (results.value[0]) choose(results.value[0])
}

function closeResults() {
  window.setTimeout(() => {
    isFocused.value = false
  }, 120)
}
</script>

<template>
  <header class="app-header">
    <div class="brand" role="img" aria-label="Knowledge Atlas">
      <svg class="brand-mark" viewBox="0 0 40 40" aria-hidden="true">
        <path d="M12 19 28 10M12 19l16 12" />
        <circle cx="10" cy="20" r="5" />
        <circle class="brand-mark__rose" cx="30" cy="9" r="4" />
        <circle class="brand-mark__amber" cx="30" cy="31" r="4" />
      </svg>
      <span>Knowledge Atlas</span>
    </div>

    <div class="global-search" :class="{ 'is-focused': isFocused }">
      <el-icon><Search /></el-icon>
      <input
        v-model="query"
        type="search"
        placeholder="搜索演示图谱，例如：事件驱动架构"
        aria-label="搜索演示知识"
        @focus="isFocused = true"
        @blur="closeResults"
        @keydown.enter="submit"
      />
      <span class="search-shortcut">⌘ K</span>
      <div v-if="isFocused && query" class="search-results">
        <button v-for="node in results" :key="node.id" type="button" @click="choose(node)">
          <span>{{ node.label }}</span>
          <small>{{ node.project }} · {{ node.subtitle }}</small>
        </button>
        <p v-if="results.length === 0">没有找到相关知识，试试“消息”或“订单”。</p>
      </div>
    </div>

    <div class="sync-status">
      <span>{{ graphActive ? '演示图谱' : '资料工作台' }}</span>
      <strong>{{ graphActive ? `${nodes.length} 个演示节点` : '项目与原文持久保存' }}</strong>
      <button type="button" aria-label="打开个人菜单">YX</button>
    </div>
  </header>
</template>
