<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Search } from '@element-plus/icons-vue'
import type { KnowledgeNode } from '../types'

const props = defineProps<{
  nodes: KnowledgeNode[]
  selectedId: string
  graphActive: boolean
  projectName?: string
}>()

const emit = defineEmits<{
  select: [id: string]
  search: [query: string]
}>()

const query = ref('')
const isFocused = ref(false)
const searchInput = ref<HTMLInputElement | null>(null)
function shortcut(event: KeyboardEvent) { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); searchInput.value?.focus() } }
onMounted(() => window.addEventListener('keydown', shortcut))
onUnmounted(() => window.removeEventListener('keydown', shortcut))

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
  if (!props.graphActive) { if (query.value.trim()) emit('search', query.value.trim()); return }
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
        ref="searchInput"
        v-model="query"
        type="search"
        :placeholder="graphActive ? '搜索独立演示图谱' : '搜索当前项目的知识、文件名或路径'"
        :aria-label="graphActive ? '搜索演示知识' : '搜索当前项目知识'"
        maxlength="200"
        @focus="isFocused = true"
        @blur="closeResults"
        @keydown.enter="submit"
      />
      <span class="search-shortcut">Ctrl K</span>
      <div v-if="graphActive && isFocused && query" class="search-results">
        <button v-for="node in results" :key="node.id" type="button" @click="choose(node)">
          <span>{{ node.label }}</span>
          <small>{{ node.project }} · {{ node.subtitle }}</small>
        </button>
        <p v-if="results.length === 0">没有找到相关知识，试试“消息”或“订单”。</p>
      </div>
    </div>

    <div class="sync-status">
      <span>{{ graphActive ? '独立演示' : '当前项目' }}</span>
      <strong>{{ graphActive ? `${nodes.length} 个演示节点` : projectName || '尚未选择' }}</strong>
    </div>
  </header>
</template>
