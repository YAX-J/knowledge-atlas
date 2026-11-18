<script setup lang="ts">
import { ref, watch } from 'vue'
import { sourceTypeLabel } from '../sourceLanguages'
import type { CodeSymbolHit, CodeSymbolSearchInput, CodeSymbolSearchResult, SourceRepositoryList } from '../api/knowledgeAtlas'

const props = defineProps<{
  repositories: SourceRepositoryList | null
  result: CodeSymbolSearchResult | null
  loading: boolean
  error: string
  locked: boolean
}>()
const emit = defineEmits<{
  search: [input: CodeSymbolSearchInput]
  clear: []
  retry: []
  open: [hit: CodeSymbolHit]
}>()
const query = ref('')
const repositoryId = ref('')
const kind = ref<CodeSymbolSearchInput['kind']>('')
const input = ref<HTMLInputElement | null>(null)
watch([query, repositoryId, kind], () => emit('clear'))
watch(() => props.repositories?.items, items => {
  if (repositoryId.value && items && !items.some(item => item.id === repositoryId.value)) repositoryId.value = ''
})
function submit() {
  if (query.value.trim()) emit('search', { query: query.value.trim(), repositoryId: repositoryId.value, kind: kind.value })
}
function clear() {
  query.value = repositoryId.value = ''
  kind.value = ''
  emit('clear')
  input.value?.focus()
}
const kindLabels = { type: '类型', field: '字段/属性', method: '函数/方法' }
</script>

<template>
  <section class="code-search" aria-labelledby="code-search-title" :aria-busy="loading">
    <div class="source-section-heading"><h3 id="code-search-title" tabindex="-1">代码符号检索</h3><span class="muted-copy">多语言 · 只读定位</span></div>
    <p class="source-upload-hint">按名称或文件路径查找已解析的类型、字段与方法，可跳转到原文。结果来自源码结构，不是已审核知识。</p>
    <form class="code-search-form" @submit.prevent="submit">
      <label class="code-search-query">符号名称或文件路径
        <input ref="input" v-model="query" type="search" maxlength="200" required placeholder="例如：OrderService、save 或 src/order" :disabled="locked" />
      </label>
      <label>仓库范围
        <select v-model="repositoryId" :disabled="locked">
          <option value="">当前项目的全部资料</option>
          <option v-for="repository in repositories?.items ?? []" :key="repository.id" :value="repository.id">{{ repository.name }}</option>
        </select>
      </label>
      <label>符号类型
        <select v-model="kind" :disabled="locked"><option value="">全部类型</option><option value="type">类型</option><option value="field">字段/属性</option><option value="method">函数/方法</option></select>
      </label>
      <div class="code-search-actions"><button class="primary-button" type="submit" :disabled="locked || loading || !query.trim()">{{ loading ? '正在检索…' : '检索代码' }}</button><button class="text-button" type="button" :disabled="locked" @click="clear">清空检索</button></div>
    </form>
    <p v-if="repositories && repositories.total > repositories.items.length" class="muted-copy">仓库选项来自当前仓库列表页；可先翻页选择其他仓库。默认范围覆盖整个当前项目。</p>
    <p v-if="loading" class="muted-copy" role="status">正在查找已解析的多语言代码符号…</p>
    <div v-else-if="error" class="inline-error" role="alert"><p>{{ error }}</p><button type="button" class="text-button" :disabled="locked" @click="emit('retry')">重试代码检索</button></div>
    <template v-else-if="result">
      <p class="muted-copy" role="status">“{{ result.query }}” · 扫描 {{ result.scanned_source_count }} 份资料，匹配 {{ result.matched_count }} 个符号，展示 {{ result.items.length }} 个。</p>
      <p v-if="result.truncated" class="inline-error" role="status">扫描或结果达到上限，当前结果可能不完整。请缩小仓库范围或使用更精确的关键词；当前未匹配不代表整个项目中不存在。</p>
      <p v-if="result.has_syntax_errors" class="inline-error" role="status">扫描资料中存在语法错误或不支持的语法，符号结果可能不完整。</p>
      <p v-if="!result.items.length" class="empty-copy">当前扫描范围内没有匹配符号。可调整名称、路径或筛选条件；未解析的代码文件需先完成解析。</p>
      <ul v-else class="code-search-results" aria-label="代码符号检索结果">
        <li v-for="hit in result.items" :key="hit.id">
          <span class="code-search-kind">{{ sourceTypeLabel(hit.language) }} · {{ kindLabels[hit.kind] }}</span>
          <div><strong>{{ hit.qualified_name }}</strong><small>{{ hit.repository_name ? `${hit.repository_name} / ` : '' }}{{ hit.source_path }} · 第 {{ hit.start_line }}–{{ hit.end_line }} 行</small></div>
          <button class="text-button" type="button" :disabled="locked" :aria-label="`查看 ${hit.qualified_name} 的源码`" @click="emit('open', hit)">查看源码</button>
          <a v-if="hit.git_url" :href="hit.git_url" target="_blank" rel="noopener noreferrer">GitHub ↗</a>
        </li>
      </ul>
    </template>
  </section>
</template>
