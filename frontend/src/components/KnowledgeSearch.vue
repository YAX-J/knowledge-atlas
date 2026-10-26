<script setup lang="ts">
import { ref, watch } from 'vue'
import type { EmbeddingIndexStatus, EvidenceLocator, KnowledgeSearchMode, KnowledgeSearchResult } from '../types'

const props = defineProps<{
  result: KnowledgeSearchResult | null
  loading: boolean
  error: string
  errorAction: 'search' | 'rebuild' | 'inspect'
  labels: Record<string, string>
  rebuilding: boolean
  notice: string
  indexStatus?: EmbeddingIndexStatus | null
  indexStatusLoading?: boolean
  indexStatusError?: string
  embeddingJob?: import('../types').EmbeddingJob | null
  embeddingJobError?: string
}>()
const emit = defineEmits<{
  search: [query: string, types: string, mode: KnowledgeSearchMode]
  rebuild: [retryInterrupted?: boolean]
  clear: []
  retry: []
  select: [id: string]
  openEvidence: [locator: EvidenceLocator]
  inspectIndex: []
}>()
const query = ref('')
const type = ref('')
const mode = ref<KnowledgeSearchMode>('bm25')
let submitted = ''
watch(() => props.result, value => {
  // Header-initiated searches populate this form; never erase a newer unsent draft.
  if (value && (!query.value.trim() || query.value.trim() === submitted)) {
    query.value = value.query
    mode.value = value.mode
    submitted = value.query
  }
})
const fields = { name: '名称', summary: '摘要', evidence: '原文证据', provenance: '来源位置' }
const modeLabels: Record<KnowledgeSearchMode, string> = { keyword: '关键词检索', bm25: 'BM25 词法检索 · 无需模型', bm25_source: 'BM25 + 来源位置 · 无需模型', vector: '语义检索', hybrid: '混合检索', rrf: 'BM25 + 向量融合' }
function submit() { if (!props.loading && !props.rebuilding && query.value.trim()) { submitted = query.value.trim(); emit('search', submitted, type.value, mode.value) } }
function clear() { query.value = type.value = ''; submitted = ''; mode.value = 'bm25'; emit('clear') }
</script>

<template>
  <section class="knowledge-search" aria-labelledby="knowledge-search-title">
    <div class="search-heading"><h2 id="knowledge-search-title">搜索项目知识</h2><span>{{ modeLabels[mode] }}</span></div>
    <p class="search-hint">关键词模式按空格分词精确匹配；BM25 支持中英混合问题，无需模型或语义索引。语义与混合模式需要配置嵌入服务、先更新索引；混合结果包含一跳关系得分；BM25 + 向量融合按两路排名组合，不扩展图邻居。</p>
    <form class="knowledge-search-form" @submit.prevent="submit">
      <label class="query-label" for="project-knowledge-query">{{ mode === 'keyword' ? '关键词' : '问题或描述' }}<input id="project-knowledge-query" v-model="query" type="search" name="q" maxlength="200" required :placeholder="mode === 'keyword' ? '例如：PostgreSQL 存储' : '例如：如何保存并检索个人技术知识？'" /></label>
      <label for="project-search-mode">检索方式<select id="project-search-mode" v-model="mode"><option value="keyword">关键词</option><option value="bm25">BM25 · 无需模型</option><option value="bm25_source">BM25 + 来源位置</option><option value="vector">语义向量</option><option value="hybrid">混合 + 图关系</option><option value="rrf">BM25 + 向量融合</option></select></label>
      <label for="project-search-type">知识类型<select id="project-search-type" v-model="type"><option value="">全部类型</option><option v-for="(label, value) in labels" :key="value" :value="value">{{ label }}</option></select></label>
      <button type="submit" :disabled="loading || rebuilding || !query.trim()">{{ loading ? '搜索中…' : '搜索知识' }}</button>
      <button type="button" :disabled="loading || rebuilding || embeddingJob?.interrupted" @click="emit('rebuild')">{{ rebuilding ? '更新索引中…' : '更新语义索引' }}</button>
      <button type="button" @click="clear">清空搜索</button>
    </form>
    <section class="index-status" aria-label="语义索引状态">
      <button type="button" :disabled="indexStatusLoading" @click="emit('inspectIndex')">{{ indexStatusLoading ? '检查索引中…' : '刷新索引状态' }}</button>
      <p v-if="embeddingJobError" role="alert">更新状态暂不可读：{{ embeddingJobError }} 请先刷新状态再决定是否重新更新。</p>
      <template v-if="embeddingJob">
        <p v-if="embeddingJob.interrupted" role="status">上次更新已中断或失去联系。已有索引会保留；重新更新可能再次产生嵌入调用。</p>
        <p v-else-if="embeddingJob.status === 'running'" role="status">服务端仍在更新索引，刷新页面不会取消。可刷新状态查看结果。</p>
        <p v-else-if="embeddingJob.status === 'succeeded'" role="status">上次索引更新已完成：新增或刷新 {{ embeddingJob.result?.updated_count ?? 0 }} 条。</p>
        <p v-else role="status">上次索引更新未完成：{{ embeddingJob.error?.message }}</p>
        <button v-if="embeddingJob.interrupted" type="button" :disabled="rebuilding || loading" @click="emit('rebuild', true)">明确重新更新索引</button>
      </template>
      <p v-if="indexStatusError" role="alert">{{ indexStatusError }} 请刷新索引状态重试。</p>
      <template v-else-if="indexStatus && !indexStatusLoading">
        <p role="status">当前项目与时间范围：已索引 {{ indexStatus.indexed_count }}/{{ indexStatus.eligible_count }} 条，缺失 {{ indexStatus.missing_count }} 条；已检查 {{ indexStatus.scanned_count }} 条，发现 {{ indexStatus.stale_count }} 条内容过期。<span v-if="indexStatus.truncated">检查达到 {{ indexStatus.scan_limit }} 条上限，尚有知识未检查。</span></p>
        <p v-if="!indexStatus.configured">嵌入服务配置尚未就绪；BM25 仍可使用。刷新状态不会调用模型。</p>
        <p v-else-if="indexStatus.missing_count || indexStatus.stale_count">请显式更新语义索引后再使用向量相关检索。更新可能产生嵌入调用。</p>
        <p v-else-if="!indexStatus.eligible_count">此范围尚无已确认的可检索知识，请先完成资料审核。</p>
        <p v-else-if="!indexStatus.truncated">此范围内索引内容已与正式知识同步。</p>
      </template>
    </section>
    <p v-if="notice" class="search-notice" role="status">{{ notice }}</p>
    <p v-if="loading" class="search-hint" role="status">正在检索当前项目…</p>
    <div v-else-if="error" class="search-error" role="alert"><p>{{ error }}</p><button type="button" @click="errorAction === 'inspect' ? emit('inspectIndex') : errorAction === 'rebuild' ? emit('rebuild') : emit('retry')">{{ errorAction === 'inspect' ? '查看更新状态' : errorAction === 'rebuild' ? '重试更新索引' : '重试搜索' }}</button></div>
    <template v-else-if="result">
      <p class="search-hint" role="status">“{{ result.query }}”：显示 {{ result.items.length }} 条知识<span v-if="result.truncated">，结果或扫描范围已截断，请补充条件</span><span v-if="result.mode === 'vector' || result.mode === 'hybrid' || result.mode === 'rrf'">；已索引 {{ result.indexed_count }}/{{ result.eligible_count }} 条</span>。</p>
      <p v-if="result.lexical" class="search-hint">本地词法扫描 {{ result.lexical.scanned_count }}/{{ result.eligible_count }} 条正式知识；最多 {{ result.lexical.entity_limit }} 条，每条排序文本最多 {{ result.lexical.text_limit_per_entity }} 字符。BM25 得分不是置信度；支持性答案仍需核对证据。<span v-if="result.lexical.truncated_reasons.length"> 部分排序文本或候选未参与计算。</span></p>
      <p v-if="!result.items.length" class="search-hint">{{ result.mode === 'vector' || result.mode === 'hybrid' || result.mode === 'rrf' ? ((result.indexed_count ?? 0) < (result.eligible_count ?? 0) ? '语义索引尚未覆盖全部可检索知识，请先更新索引。' : '未找到相关知识，可换一种问题描述。') : '未找到匹配知识。可换一种表述，或先在资料中确认相关实体。' }}</p>
      <ol v-else class="keyword-results" aria-label="知识搜索结果">
        <li v-for="hit in result.items" :key="hit.entity.id">
          <div class="hit-heading"><button type="button" @click="emit('select', hit.entity.id)">{{ hit.entity.name }}</button><span>{{ labels[hit.entity.type] ?? hit.entity.type }}</span></div>
          <p class="hit-summary">{{ hit.entity.summary }}</p>
          <p v-if="result.mode === 'keyword'" class="hit-meta">命中：{{ hit.matched_fields.map(field => fields[field]).join('、') }} · 关键词得分 {{ hit.keyword_score }}</p>
          <p v-else-if="(result.mode === 'bm25' || result.mode === 'bm25_source')" class="hit-meta">命中：{{ hit.matched_fields.map(field => fields[field]).join('、') }} · BM25 得分 {{ (hit.bm25_score ?? 0).toFixed(3) }}</p>
          <p v-else-if="result.mode === 'vector'" class="hit-meta">向量相似度 {{ ((hit.vector_score ?? 0) * 100).toFixed(1) }}%</p>
          <p v-else-if="result.mode === 'rrf'" class="hit-meta">融合得分 {{ hit.rrf_score?.toFixed(5) }} · 词法排名 {{ hit.lexical_rank ?? '未命中' }} · 向量排名 {{ hit.vector_rank ?? '未命中' }}。排名不表示答案可信度。</p>
          <p v-else class="hit-meta">融合得分 {{ ((hit.hybrid_score ?? 0) * 100).toFixed(1) }} · 关键词 {{ ((hit.keyword_component ?? 0) * 100).toFixed(1) }}% · 向量 {{ ((hit.vector_component ?? 0) * 100).toFixed(1) }}% · 图关系 {{ ((hit.graph_score ?? 0) * 100).toFixed(1) }}%</p>
          <ul v-if="result.mode === 'hybrid' && hit.graph_connections.length" class="graph-signals" aria-label="图关系得分依据"><li v-for="signal in hit.graph_connections" :key="`${signal.relationship_id}:${signal.related_entity_id}`">经“{{ signal.relationship_name }}”关联到 {{ signal.related_entity_name }}（{{ (signal.score * 100).toFixed(1) }}%）</li></ul>
          <article v-for="evidence in hit.evidence" :key="evidence.id" class="search-evidence"><strong>{{ evidence.title }}</strong><span>第 {{ evidence.start_line }}–{{ evidence.end_line }} 行</span><a v-if="evidence.git_url" :href="evidence.git_url" target="_blank" rel="noopener noreferrer">GitHub 原文 ↗</a><blockquote>{{ evidence.quote }}</blockquote><button type="button" class="evidence-source-button" @click="emit('openEvidence', evidence)">查看原文分块</button></article>
          <p v-if="!hit.evidence.length" class="hit-meta">暂无可访问的原文证据。</p>
        </li>
      </ol>
    </template>
  </section>
</template>

<style scoped>
.index-status { margin: 14px 0; padding: 12px; border-left: 2px solid var(--teal); background: #edf5f3; font-size: 12px; line-height: 1.8; }
.knowledge-search { margin: 22px 0; padding: 18px; border: 1px solid var(--line); border-radius: 7px; background: var(--paper); min-width: 0; }
.search-heading, .hit-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }.search-heading h2 { margin: 0; font-size: 16px; }.search-heading > span, .hit-heading > span { color: var(--teal); font-size: 11px; }
.search-hint, .hit-meta, .search-notice { font-size: 12px; color: #536b70; line-height: 1.8; overflow-wrap: anywhere; }.search-notice { color: var(--teal); }
.knowledge-search-form { display: flex; align-items: end; flex-wrap: wrap; gap: 10px; }.knowledge-search-form label { display: grid; gap: 7px; font-size: 12px; min-width: 0; }.query-label { flex: 1 1 260px; }
input, select, button { min-height: 40px; border: 1px solid #aabec0; border-radius: 5px; background: var(--paper); color: var(--ink); padding: 8px 12px; font: inherit; font-size: 12px; }input { width: 100%; min-width: 0; }button { cursor: pointer; }button[type=submit] { color: white; background: var(--ink); }button:disabled { opacity: .5; cursor: not-allowed; }
.keyword-results { list-style: none; margin: 0; padding: 0; display: grid; gap: 14px; max-height: 520px; overflow: auto; }.keyword-results li { padding: 16px; border: 1px solid var(--line); border-radius: 5px; min-width: 0; }.hit-heading button { max-width: 100%; text-align: left; overflow-wrap: anywhere; color: var(--teal); font-weight: 600; }.hit-summary { font-size: 13px; line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; }.hit-meta { font-size: 11px; }
.search-evidence { padding: 10px 12px; margin-top: 8px; border-left: 2px solid #a3b9b7; background: #edf5f3; font-size: 12px; overflow-wrap: anywhere; }.search-evidence span { margin-left: 10px; color: #536b70; font-size: 11px; }.search-evidence a { margin-left: 10px; color: var(--teal); }.search-evidence blockquote { margin: 8px 0 0; white-space: pre-wrap; line-height: 1.8; }.search-error { color: #91274d; font-size: 13px; overflow-wrap: anywhere; }
.graph-signals { margin: 8px 0; padding-left: 18px; color: #3f656a; font-size: 11px; line-height: 1.7; overflow-wrap: anywhere; }
@media (max-width: 760px) { .knowledge-search { padding: 14px; }.knowledge-search-form .query-label { flex-basis: 100%; }.keyword-results { max-height: 440px; }.keyword-results li { padding: 12px; } }
</style>
