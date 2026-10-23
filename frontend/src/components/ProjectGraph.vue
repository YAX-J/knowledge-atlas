<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import KnowledgeSearch from './KnowledgeSearch.vue'
import type { ApiProject } from '../api/knowledgeAtlas'
import type { EntityDetail, EvidenceLocator, FormalKnowledgeEdge, KnowledgeSearchMode, KnowledgeSearchResult, ProjectGraphData, RelationshipDetail } from '../types'

const props = defineProps<{
  project: ApiProject | null
  graph: ProjectGraphData | null
  entityDetail: EntityDetail | null
  relationshipDetail: RelationshipDetail | null
  loading: boolean
  detailLoading: boolean
  error: string
  detailError: string
  selectedId: string
  center: string
  depth: number
  typeFilter: string
  searchResult: KnowledgeSearchResult | null
  searchLoading: boolean
  searchError: string
  searchErrorAction: 'search' | 'rebuild'
  searchRebuilding: boolean
  searchNotice: string
  validAt: string
  mutationBusy: boolean
}>()
const emit = defineEmits<{
  back: []
  demo: []
  refresh: []
  retryDetail: []
  selectEntity: [id: string]
  selectRelationship: [id: string]
  neighborhood: [id: string]
  reset: []
  filterType: [value: string]
  depth: [value: number]
  search: [query: string, types: string, mode: KnowledgeSearchMode]
  rebuildSearch: []
  clearSearch: []
  retrySearch: []
  selectSearchEntity: [id: string]
  openEvidence: [locator: EvidenceLocator]
  time: [value: string]
}>()
const localTime = ref('')
watch(() => props.validAt, value => {
  if (!value) { localTime.value = ''; return }
  const date = new Date(value)
  localTime.value = new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 23)
}, { immediate: true })
function applyTime() { emit('time', localTime.value ? new Date(localTime.value).toISOString() : '') }
const labels: Record<string, string> = {
  Project: '项目', CodeFile: '代码文件', CodeEntity: '代码实体', Technology: '技术', Concept: '概念',
  Problem: '问题', Solution: '方案', Decision: '决策', Alternative: '候选方案', Constraint: '约束',
}
const layout = computed(() => {
  const nodes = props.graph?.nodes ?? []
  const columns = Math.min(4, Math.max(1, nodes.length))
  return { columns, width: Math.max(740, columns * 250), height: Math.max(300, Math.ceil(nodes.length / columns) * 150 + 60) }
})
const positioned = computed(() => (props.graph?.nodes ?? []).map((item, index) => ({
  ...item, x: layout.value.width / 2 + (index % layout.value.columns - (layout.value.columns - 1) / 2) * 250,
  y: 90 + Math.floor(index / layout.value.columns) * 150,
})))
const positions = computed(() => new Map(positioned.value.map(item => [item.id, item])))
const selected = computed(() => props.entityDetail?.entity ?? props.relationshipDetail?.relationship ?? null)
const evidence = computed(() => props.entityDetail?.evidence ?? props.relationshipDetail?.evidence ?? [])
function edgePath(edge: FormalKnowledgeEdge) {
  const source = positions.value.get(edge.source_id)
  const target = positions.value.get(edge.target_id)
  if (!source || !target) return ''
  if (source.id === target.id) return `M${source.x - 50},${source.y - 34} C${source.x - 110},${source.y - 115} ${source.x + 110},${source.y - 115} ${source.x + 50},${source.y - 34}`
  const dx = target.x - source.x, dy = target.y - source.y
  const ratio = Math.max(Math.abs(dx) / 102, Math.abs(dy) / 38)
  return `M${source.x + dx / ratio},${source.y + dy / ratio} L${target.x - dx / ratio},${target.y - dy / ratio}`
}
function filter(event: Event) { emit('filterType', (event.target as HTMLSelectElement).value) }
function depthChange(event: Event) { emit('depth', Number((event.target as HTMLSelectElement).value)) }
</script>

<template>
  <main class="project-graph-page" aria-labelledby="project-graph-title">
    <header class="graph-page-heading">
      <div><span class="graph-kicker">项目知识 / 已确认</span><h1 id="project-graph-title">{{ project?.name ?? '项目图谱' }}</h1><p>沿着关系找回原文，让每条知识都有依据。</p></div>
      <div class="graph-actions"><button type="button" :disabled="mutationBusy" @click="emit('back')">返回资料</button><button type="button" :disabled="mutationBusy" @click="emit('demo')">演示图谱</button><button type="button" :disabled="loading || mutationBusy" @click="emit('refresh')">刷新图谱</button></div>
    </header>
    <KnowledgeSearch :key="project?.id" :result="searchResult" :loading="searchLoading" :error="searchError" :error-action="searchErrorAction" :labels="labels"
      :rebuilding="searchRebuilding" :notice="searchNotice"
      @search="(query, types, mode) => emit('search', query, types, mode)" @rebuild="emit('rebuildSearch')"
      @clear="emit('clearSearch')" @retry="emit('retrySearch')" @select="id => emit('selectSearchEntity', id)" @open-evidence="emit('openEvidence', $event)" />
    <div class="graph-toolbar">
      <span class="graph-real-label">真实项目图谱</span>
      <form class="time-query" @submit.prevent="applyTime"><label>历史时间 <input v-model="localTime" type="datetime-local" step="0.001" :disabled="loading || mutationBusy" /></label><button type="submit" :disabled="loading || mutationBusy">查询该时刻</button><button v-if="validAt" type="button" :disabled="loading || mutationBusy" @click="emit('time', '')">返回当前知识</button></form>
      <span v-if="validAt" class="graph-kicker">历史视图 · {{ new Date(validAt).toLocaleString('zh-CN') }}</span>
      <label>知识类型 <select :value="typeFilter" :disabled="loading" @change="filter"><option value="">全部类型</option><option v-for="(label, type) in labels" :key="type" :value="type">{{ label }}</option></select></label>
      <label>邻域深度 <select :value="depth" :disabled="loading || !center" @change="depthChange"><option value="1">一跳</option><option value="2">二跳</option></select></label>
      <button v-if="center" type="button" :disabled="loading" @click="emit('reset')">返回项目总览</button>
      <span v-if="graph" class="graph-count">{{ graph.nodes.length }} 个节点 · {{ graph.edges.length }} 条关系</span>
    </div>
    <p v-if="loading" class="graph-message" role="status">正在读取已确认知识…</p>
    <div v-else-if="error" class="graph-message graph-error" role="alert"><p>{{ error }}</p><button type="button" @click="emit('refresh')">重试加载图谱</button></div>
    <div v-else-if="graph?.nodes.length === 0" class="graph-empty"><span aria-hidden="true">◇</span><h2>这里还没有符合条件的知识</h2><p>在资料中提取并确认实体，再确认它们之间的关系。已确认的旧候选可点击“补写入图谱”。</p><button type="button" @click="emit('back')">前往资料审核</button></div>
    <template v-else-if="graph">
      <p v-if="graph.truncated" class="graph-message" role="status">当前只展示部分知识。可按类型筛选，或选择节点后查看它的一跳、二跳邻域。</p>
      <div class="real-graph-layout">
        <section class="real-graph-canvas" aria-label="已确认知识关系图">
          <p class="graph-scroll-hint">画布可横向滚动，也可使用下方列表选择节点与关系。</p>
          <div class="graph-scroll-area" tabindex="0" aria-label="图谱画布滚动区域">
            <svg :viewBox="`0 0 ${layout.width} ${layout.height}`" :style="{ width: `${layout.width}px`, height: `${layout.height}px` }" role="group" aria-label="真实项目知识图谱">
              <defs><marker id="real-graph-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="#718f94" /></marker></defs>
              <g v-for="edge in graph.edges" :key="edge.id" class="real-edge" :class="{ selected: edge.id === selectedId }" role="button" tabindex="0" :aria-label="`查看关系：${edge.name}`" @click="emit('selectRelationship', edge.id)" @keydown.enter="emit('selectRelationship', edge.id)" @keydown.space.prevent="emit('selectRelationship', edge.id)">
                <path :d="edgePath(edge)" class="edge-hit" /><path :d="edgePath(edge)" marker-end="url(#real-graph-arrow)" />
              </g>
              <g v-for="node in positioned" :key="node.id" :transform="`translate(${node.x} ${node.y})`" class="real-node" :class="{ selected: selectedId === node.id }" role="button" tabindex="0" :aria-label="`查看知识：${node.name}`" @click="emit('selectEntity', node.id)" @keydown.enter="emit('selectEntity', node.id)" @keydown.space.prevent="emit('selectEntity', node.id)">
                <title>{{ node.name }}</title><rect x="-98" y="-34" width="196" height="68" rx="8" /><text y="-8" text-anchor="middle" class="real-node-kind">{{ labels[node.type] ?? node.type }}</text><text y="15" text-anchor="middle">{{ node.name.length > 13 ? node.name.slice(0, 13) + '…' : node.name }}</text>
              </g>
            </svg>
          </div>
          <details class="graph-records"><summary>节点与关系列表</summary><h2>知识节点</h2><button v-for="node in graph.nodes" :key="node.id" type="button" :aria-pressed="selectedId === node.id" @click="emit('selectEntity', node.id)">{{ node.name }} <small>{{ labels[node.type] ?? node.type }}</small></button><h2>知识关系</h2><p v-if="!graph.edges.length">尚无已确认关系。</p><button v-for="edge in graph.edges" :key="edge.id" type="button" :aria-pressed="selectedId === edge.id" @click="emit('selectRelationship', edge.id)">{{ edge.name }} <small>{{ edge.type }}</small></button></details>
        </section>
        <aside id="formal-knowledge-detail" class="formal-detail" tabindex="-1" aria-label="正式知识与原文证据" :aria-busy="detailLoading">
          <p v-if="detailLoading" role="status">正在读取知识详情…</p>
          <div v-else-if="detailError" class="graph-error" role="alert"><p>{{ detailError }}</p><button type="button" @click="emit('retryDetail')">重试读取详情</button></div>
          <template v-else-if="selected">
            <span class="graph-kicker">{{ entityDetail ? '知识节点' : '知识关系' }} · {{ labels[selected.type] ?? selected.type }}</span><h2>{{ selected.name }}</h2><p class="formal-summary">{{ selected.summary }}</p>
            <dl><div><dt>确认状态</dt><dd>已确认</dd></div><div><dt>知识状态</dt><dd>{{ selected.status === 'superseded' ? '已被替代（历史有效）' : selected.status === 'active' ? '有效' : selected.status }}</dd></div><div><dt>模型置信度</dt><dd>{{ Math.round(selected.confidence * 100) }}%</dd></div><div><dt>有效起点</dt><dd>{{ new Date(selected.valid_from).toLocaleString('zh-CN') }}</dd></div><div v-if="selected.valid_to"><dt>有效截止</dt><dd>{{ new Date(selected.valid_to).toLocaleString('zh-CN') }}</dd></div></dl>
            <button v-if="entityDetail" class="graph-primary" type="button" @click="emit('neighborhood', selected.id)">以此知识为中心</button>
            <div v-if="relationshipDetail" class="graph-actions"><button type="button" @click="emit('neighborhood', relationshipDetail.relationship.source_id)">查看来源节点</button><button type="button" @click="emit('neighborhood', relationshipDetail.relationship.target_id)">查看目标节点</button></div>
            <h3>原文证据 <span>{{ evidence.length }}</span></h3>
            <p v-if="!evidence.length">暂无可访问的原文证据。</p>
            <article v-for="item in evidence" :key="item.id" class="formal-evidence"><strong>{{ item.title }}</strong><a v-if="item.git_url" :href="item.git_url" target="_blank" rel="noopener noreferrer">GitHub 原文 ↗</a><small>第 {{ item.start_line }}–{{ item.end_line }} 行 · {{ item.heading_path.join(' / ') || '文档开头' }}</small><blockquote>{{ item.quote }}</blockquote><button type="button" class="evidence-source-button" @click="emit('openEvidence', item)">查看原文分块</button></article>
            <template v-if="entityDetail"><h3>直接关系</h3><p v-if="!entityDetail.relationships.length">还没有已确认的直接关系。</p><button v-for="edge in entityDetail.relationships" :key="edge.id" type="button" class="formal-relation" @click="emit('selectRelationship', edge.id)">{{ edge.name }} <small>{{ edge.type }}</small></button><p v-if="entityDetail.truncated">仅展示前 100 条直接关系。</p></template>
          </template>
        </aside>
      </div>
    </template>
    <slot name="evolution" />
  </main>
</template>

<style scoped>
.time-query { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }.time-query input { min-width: 0; max-width: 100%; min-height: 40px; padding: 6px; border: 1px solid #aabec0; border-radius: 5px; color: var(--ink); background: var(--paper); box-sizing: border-box; }.time-query input:focus-visible { outline: 2px solid var(--rose); outline-offset: 3px; }
.project-graph-page { height: calc(100% - 86px); overflow: auto; padding: 30px 30px 60px 100px; background: #edf3f3; color: var(--ink); }
.graph-page-heading { display: flex; justify-content: space-between; gap: 20px; align-items: center; }
.graph-kicker { color: var(--teal); font-size: 12px; }
h1 { margin: 9px 0; font: 500 32px "Noto Serif SC", SimSun, serif; overflow-wrap: anywhere; }
.graph-page-heading p, .graph-scroll-hint { color: #536b70; font-size: 12px; line-height: 1.8; }
button, select { min-height: 40px; padding: 8px 12px; border: 1px solid #aabec0; border-radius: 5px; color: var(--ink); background: var(--paper); cursor: pointer; font-size: 12px; }
button:disabled, select:disabled { opacity: .5; cursor: not-allowed; }
.graph-actions, .graph-toolbar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.graph-toolbar { margin: 22px 0; padding: 14px; border: 1px solid var(--line); background: #f8fbfb; border-radius: 6px; font-size: 12px; }
.graph-toolbar label { display: flex; align-items: center; gap: 8px; }
.graph-real-label { padding: 6px 9px; color: #245c4e; background: #dceee7; border-radius: 4px; }
.graph-count { margin-left: auto; color: #536b70; }
.graph-message { padding: 15px; background: #f8fbfb; font-size: 13px; line-height: 1.8; }
.graph-error { color: #91274d; overflow-wrap: anywhere; }
.graph-empty { display: grid; justify-items: center; padding: 70px 20px; border: 1px solid var(--line); background: var(--paper); text-align: center; }
.graph-empty > span { font-size: 52px; color: var(--teal); }
.graph-empty h2 { font-size: 20px; }.graph-empty p { max-width: 460px; font-size: 13px; line-height: 1.9; color: #536b70; }
.real-graph-layout { display: grid; grid-template-columns: minmax(0, 1fr) 330px; align-items: start; gap: 20px; }
.real-graph-canvas, .formal-detail { min-width: 0; border: 1px solid var(--line); border-radius: 7px; background: #f8fbfb; overflow: hidden; }
.graph-scroll-hint { margin: 12px 16px; }.graph-scroll-area { max-height: 600px; overflow: auto; background-image: radial-gradient(#c6d7d8 .8px, transparent .8px); background-size: 20px 20px; }
svg { display: block; }.real-edge path { stroke: #718f94; stroke-width: 1.6; fill: none; }.real-edge .edge-hit { stroke: transparent; stroke-width: 14; }.real-edge.selected path:not(.edge-hit), .real-edge:focus-visible path:not(.edge-hit) { stroke: var(--rose); stroke-width: 3; }
.real-node { cursor: pointer; }.real-node rect { stroke: #91afb2; fill: #edf6f5; stroke-width: 1.5; }.real-node.selected rect, .real-node:focus-visible rect { stroke: var(--rose); fill: #f7edf1; stroke-width: 2.5; }.real-node text { fill: var(--ink); font-size: 13px; pointer-events: none; }.real-node text.real-node-kind { fill: var(--teal); font-size: 10px; }
.graph-records { padding: 16px; border-top: 1px solid var(--line); }.graph-records summary { cursor: pointer; font-size: 13px; }.graph-records h2 { font-size: 13px; margin-top: 20px; }.graph-records button, .formal-relation { display: block; width: 100%; margin-top: 8px; text-align: left; overflow-wrap: anywhere; }.graph-records button[aria-pressed=true] { border-color: var(--rose); background: #f7edf1; }small { display: block; margin-top: 6px; color: #536b70; font-size: 11px; }
.formal-detail { padding: 20px; }.formal-detail h2 { margin: 12px 0; font-size: 19px; line-height: 1.6; overflow-wrap: anywhere; }.formal-summary { font-size: 13px; line-height: 1.9; white-space: pre-wrap; overflow-wrap: anywhere; }.formal-detail dl { font-size: 11px; color: #536b70; }.formal-detail dl > div { display: flex; gap: 12px; justify-content: space-between; margin: 12px 0; }.formal-detail dd { margin: 0; text-align: right; }.formal-detail h3 { margin: 24px 0 12px; font-size: 14px; }.formal-detail h3 span { color: #536b70; }.graph-primary { background: var(--ink); color: white; border-color: var(--ink); }
.formal-evidence { margin-top: 12px; padding: 12px; border: 1px solid var(--line); border-radius: 5px; font-size: 12px; overflow-wrap: anywhere; }.formal-evidence a { display: inline-block; margin: 6px 0 0 8px; color: var(--teal); }.formal-evidence blockquote { margin: 12px 0 0; padding-left: 10px; border-left: 2px solid #a3b9b7; white-space: pre-wrap; font-size: 12px; line-height: 1.9; }
@media (max-width: 1100px) { .real-graph-layout { grid-template-columns: minmax(0, 1fr); }.graph-page-heading { align-items: start; flex-direction: column; } }
@media (max-width: 760px) { .project-graph-page { height: calc(100% - 72px); padding: 22px 16px 115px; }h1 { font-size: 27px; }.graph-count { margin-left: 0; }.graph-toolbar { align-items: start; flex-direction: column; }.formal-detail { padding: 16px; }.graph-scroll-area { max-height: 360px; } }
</style>
