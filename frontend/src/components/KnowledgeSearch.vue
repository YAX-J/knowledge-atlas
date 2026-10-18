<script setup lang="ts">
import { ref } from 'vue'
import type { KnowledgeSearchMode, KnowledgeSearchResult } from '../types'

defineProps<{
  result: KnowledgeSearchResult | null
  loading: boolean
  error: string
  errorAction: 'search' | 'rebuild'
  labels: Record<string, string>
  rebuilding: boolean
  notice: string
}>()
const emit = defineEmits<{
  search: [query: string, types: string, mode: KnowledgeSearchMode]
  rebuild: []
  clear: []
  retry: []
  select: [id: string]
}>()
const query = ref('')
const type = ref('')
const mode = ref<KnowledgeSearchMode>('keyword')
const fields = { name: '名称', summary: '摘要', evidence: '原文证据' }
const modeLabels: Record<KnowledgeSearchMode, string> = { keyword: '关键词检索', vector: '语义检索', hybrid: '混合检索' }
function submit() { if (query.value.trim()) emit('search', query.value.trim(), type.value, mode.value) }
function clear() { query.value = type.value = ''; mode.value = 'keyword'; emit('clear') }
</script>

<template>
  <section class="knowledge-search" aria-labelledby="knowledge-search-title">
    <div class="search-heading"><h2 id="knowledge-search-title">搜索项目知识</h2><span>{{ modeLabels[mode] }}</span></div>
    <p class="search-hint">关键词模式精确匹配原文；语义模式召回相似知识；混合模式再融合一跳关系，并展示各路得分。语义与混合模式需要先更新索引。</p>
    <form class="knowledge-search-form" @submit.prevent="submit">
      <label class="query-label" for="project-knowledge-query">{{ mode === 'keyword' ? '关键词' : '问题或描述' }}<input id="project-knowledge-query" v-model="query" type="search" name="q" maxlength="200" required :placeholder="mode === 'keyword' ? '例如：PostgreSQL 存储' : '例如：如何保存并检索个人技术知识？'" /></label>
      <label for="project-search-mode">检索方式<select id="project-search-mode" v-model="mode"><option value="keyword">关键词</option><option value="vector">语义向量</option><option value="hybrid">混合 + 图关系</option></select></label>
      <label for="project-search-type">知识类型<select id="project-search-type" v-model="type"><option value="">全部类型</option><option v-for="(label, value) in labels" :key="value" :value="value">{{ label }}</option></select></label>
      <button type="submit" :disabled="loading || rebuilding || !query.trim()">{{ loading ? '搜索中…' : '搜索知识' }}</button>
      <button type="button" :disabled="loading || rebuilding" @click="emit('rebuild')">{{ rebuilding ? '更新索引中…' : '更新语义索引' }}</button>
      <button type="button" @click="clear">清空搜索</button>
    </form>
    <p v-if="notice" class="search-notice" role="status">{{ notice }}</p>
    <p v-if="loading" class="search-hint" role="status">正在检索当前项目…</p>
    <div v-else-if="error" class="search-error" role="alert"><p>{{ error }}</p><button type="button" @click="errorAction === 'rebuild' ? emit('rebuild') : emit('retry')">{{ errorAction === 'rebuild' ? '重试更新索引' : '重试搜索' }}</button></div>
    <template v-else-if="result">
      <p class="search-hint" role="status">“{{ result.query }}”：找到 {{ result.items.length }} 条知识<span v-if="result.truncated">，仅展示前 10 条，请补充条件</span><span v-if="result.mode !== 'keyword'">；已索引 {{ result.indexed_count }}/{{ result.eligible_count }} 条</span>。</p>
      <p v-if="!result.items.length" class="search-hint">{{ result.mode !== 'keyword' ? ((result.indexed_count ?? 0) < (result.eligible_count ?? 0) ? '语义索引尚未覆盖全部可检索知识，请先更新索引。' : '未找到相关知识，可换一种问题描述。') : '未找到匹配知识。可减少关键词，或先在资料中确认相关实体。' }}</p>
      <ol v-else class="keyword-results" aria-label="知识搜索结果">
        <li v-for="hit in result.items" :key="hit.entity.id">
          <div class="hit-heading"><button type="button" @click="emit('select', hit.entity.id)">{{ hit.entity.name }}</button><span>{{ labels[hit.entity.type] ?? hit.entity.type }}</span></div>
          <p class="hit-summary">{{ hit.entity.summary }}</p>
          <p v-if="result.mode === 'keyword'" class="hit-meta">命中：{{ hit.matched_fields.map(field => fields[field]).join('、') }} · 关键词得分 {{ hit.keyword_score }}</p>
          <p v-else-if="result.mode === 'vector'" class="hit-meta">向量相似度 {{ ((hit.vector_score ?? 0) * 100).toFixed(1) }}%</p>
          <p v-else class="hit-meta">融合得分 {{ ((hit.hybrid_score ?? 0) * 100).toFixed(1) }} · 关键词 {{ ((hit.keyword_component ?? 0) * 100).toFixed(1) }}% · 向量 {{ ((hit.vector_component ?? 0) * 100).toFixed(1) }}% · 图关系 {{ ((hit.graph_score ?? 0) * 100).toFixed(1) }}%</p>
          <ul v-if="result.mode === 'hybrid' && hit.graph_connections.length" class="graph-signals" aria-label="图关系得分依据"><li v-for="signal in hit.graph_connections" :key="`${signal.relationship_id}:${signal.related_entity_id}`">经“{{ signal.relationship_name }}”关联到 {{ signal.related_entity_name }}（{{ (signal.score * 100).toFixed(1) }}%）</li></ul>
          <article v-for="evidence in hit.evidence" :key="evidence.id" class="search-evidence"><strong>{{ evidence.title }}</strong><span>第 {{ evidence.start_line }}–{{ evidence.end_line }} 行</span><blockquote>{{ evidence.quote }}</blockquote></article>
          <p v-if="!hit.evidence.length" class="hit-meta">暂无可访问的原文证据。</p>
        </li>
      </ol>
    </template>
  </section>
</template>

<style scoped>
.knowledge-search { margin: 22px 0; padding: 18px; border: 1px solid var(--line); border-radius: 7px; background: var(--paper); min-width: 0; }
.search-heading, .hit-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }.search-heading h2 { margin: 0; font-size: 16px; }.search-heading > span, .hit-heading > span { color: var(--teal); font-size: 11px; }
.search-hint, .hit-meta, .search-notice { font-size: 12px; color: #536b70; line-height: 1.8; overflow-wrap: anywhere; }.search-notice { color: var(--teal); }
.knowledge-search-form { display: flex; align-items: end; flex-wrap: wrap; gap: 10px; }.knowledge-search-form label { display: grid; gap: 7px; font-size: 12px; min-width: 0; }.query-label { flex: 1 1 260px; }
input, select, button { min-height: 40px; border: 1px solid #aabec0; border-radius: 5px; background: var(--paper); color: var(--ink); padding: 8px 12px; font: inherit; font-size: 12px; }input { width: 100%; min-width: 0; }button { cursor: pointer; }button[type=submit] { color: white; background: var(--ink); }button:disabled { opacity: .5; cursor: not-allowed; }
.keyword-results { list-style: none; margin: 0; padding: 0; display: grid; gap: 14px; max-height: 520px; overflow: auto; }.keyword-results li { padding: 16px; border: 1px solid var(--line); border-radius: 5px; min-width: 0; }.hit-heading button { max-width: 100%; text-align: left; overflow-wrap: anywhere; color: var(--teal); font-weight: 600; }.hit-summary { font-size: 13px; line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; }.hit-meta { font-size: 11px; }
.search-evidence { padding: 10px 12px; margin-top: 8px; border-left: 2px solid #a3b9b7; background: #edf5f3; font-size: 12px; overflow-wrap: anywhere; }.search-evidence span { margin-left: 10px; color: #536b70; font-size: 11px; }.search-evidence blockquote { margin: 8px 0 0; white-space: pre-wrap; line-height: 1.8; }.search-error { color: #91274d; font-size: 13px; overflow-wrap: anywhere; }
.graph-signals { margin: 8px 0; padding-left: 18px; color: #3f656a; font-size: 11px; line-height: 1.7; overflow-wrap: anywhere; }
@media (max-width: 760px) { .knowledge-search { padding: 14px; }.knowledge-search-form .query-label { flex-basis: 100%; }.keyword-results { max-height: 440px; }.keyword-results li { padding: 12px; } }
</style>
