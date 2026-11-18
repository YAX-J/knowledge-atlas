<script setup lang="ts">
import { computed, ref, watch, watchPostEffect } from 'vue'
import KnowledgeSearch from './KnowledgeSearch.vue'
import type { GraphSection } from '../composables/useWorkspaceRoute'
import type { ApiProject } from '../api/knowledgeAtlas'
import type { EmbeddingJob, EmbeddingIndexStatus, EntityDetail, EvidenceLocator, FormalKnowledgeEdge, GraphBackend, GraphTimeline, KnowledgeSearchMode, KnowledgeSearchResult, Neo4jSnapshot, ProjectGraphData, RelationshipDetail } from '../types'

const props = defineProps<{
  project: ApiProject | null
  section?: GraphSection
  graph: ProjectGraphData | null
  backend?: GraphBackend
  neo4jSnapshot?: Neo4jSnapshot | null
  neo4jSyncing?: boolean
  neo4jSyncError?: string
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
  searchErrorAction: 'search' | 'rebuild' | 'inspect'
  searchRebuilding: boolean
  searchNotice: string
  validAt: string
  mutationBusy: boolean
  timeline?: GraphTimeline | null
  timelineLoading?: boolean
  timelineError?: string
  indexStatus?: EmbeddingIndexStatus | null
  indexStatusLoading?: boolean
  indexStatusError?: string
  embeddingJob?: EmbeddingJob | null
  embeddingJobError?: string
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
  rebuildSearch: [retryInterrupted?: boolean]
  clearSearch: []
  retrySearch: []
  selectSearchEntity: [id: string]
  openEvidence: [locator: EvidenceLocator]
  time: [value: string]
  retryTimeline: []
  inspectIndex: []
  section: [value: GraphSection]
  backend: [value: GraphBackend]
  syncNeo4j: []
}>()
const localTime = ref('')
watch(() => props.validAt, value => {
  if (!value) { localTime.value = ''; return }
  const date = new Date(value)
  localTime.value = new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 23)
}, { immediate: true })
function applyTime() {
  if (!localTime.value) { emit('time', ''); return }
  const selected = new Date(localTime.value).toISOString()
  emit('time', props.validAt && new Date(props.validAt).toISOString() === selected ? props.validAt : selected)
}
function instantKey(value: string) {
  const millis = new Date(value).toISOString().slice(0, -1)
  const fraction = value.match(/\.(\d{4,6})Z$/)?.[1]
  return millis + (fraction?.padEnd(6, '0').slice(3) ?? '000')
}
const stops = computed(() => {
  const entries = new Map((props.timeline?.instants ?? []).map(value => [instantKey(value), value]))
  if (props.validAt) entries.set(instantKey(props.validAt), props.validAt)
  return [...entries.keys()].sort().map(key => entries.get(key)!)
})
const previewIndex = ref<number | null>(null)
const activeIndex = computed(() => props.validAt ? stops.value.indexOf(props.validAt) : stops.value.length)
const sliderIndex = computed(() => previewIndex.value ?? activeIndex.value)
const sliderTime = computed(() => stops.value[sliderIndex.value])
function displayInstant(value: string) {
  const fraction = instantKey(value).split('.')[1]?.replace(/0+$/, '')
  return new Date(value).toLocaleString('zh-CN') + (fraction ? `.${fraction}` : '')
}
watch([stops, () => props.validAt], () => { previewIndex.value = null })
function selectTimeline(event: Event) {
  const value = stops.value[(event.target as HTMLInputElement).valueAsNumber] ?? ''
  previewIndex.value = null
  if (value !== props.validAt) emit('time', value)
}
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
const isNeo4j = computed(() => props.backend === 'neo4j')
const searchPane = ref<HTMLElement | null>(null)
watchPostEffect(onCleanup => {
  const pane = searchPane.value
  if (props.section !== 'search' || !pane) return
  // Wait for v-show to make the search input focusable.
  const frame = requestAnimationFrame(() => pane.querySelector<HTMLInputElement>('input[type="search"]')?.focus())
  onCleanup(() => cancelAnimationFrame(frame))
})
const labelsVisible = computed(() => (props.graph?.nodes.length ?? 0) <= 50)
const graphKinds = computed(() => [...new Set(props.graph?.nodes.map(node => node.type) ?? [])])
function ended(edge: FormalKnowledgeEdge) {
  return Boolean(props.validAt && !isNeo4j.value && (edge.status === 'superseded' ||
    (edge.valid_to && Date.parse(edge.valid_to) <= Date.now())))
}
const hasEndedEdges = computed(() => props.graph?.edges.some(ended))
function edgePath(edge: FormalKnowledgeEdge) {
  const source = positions.value.get(edge.source_id)
  const target = positions.value.get(edge.target_id)
  if (!source || !target) return ''
  if (source.id === target.id) return `M${source.x - 50},${source.y - 34} C${source.x - 110},${source.y - 115} ${source.x + 110},${source.y - 115} ${source.x + 50},${source.y - 34}`
  const dx = target.x - source.x, dy = target.y - source.y
  function edgeOffset(type: string) {
    if (type === 'Decision' || type === 'Technology' || type === 'Concept') return 38 / Math.hypot(dx, dy)
    if (type === 'Problem') return 1 / (Math.abs(dx) / 102 + Math.abs(dy) / 38)
    return 1 / Math.max(Math.abs(dx) / 102, Math.abs(dy) / 38)
  }
  const start = edgeOffset(source.type)
  const end = edgeOffset(target.type)
  return `M${source.x + dx * start},${source.y + dy * start} L${target.x - dx * end},${target.y - dy * end}`
}
function filter(event: Event) { emit('filterType', (event.target as HTMLSelectElement).value) }
function depthChange(event: Event) { emit('depth', Number((event.target as HTMLSelectElement).value)) }
</script>

<template>
  <main class="project-graph-page" aria-labelledby="project-graph-title">
    <header class="graph-page-heading graph-page-toolbar">
      <h1 id="project-graph-title" class="visually-hidden">项目知识图谱</h1>
      <nav class="graph-sections" aria-label="知识工作区"><button v-for="tab in ([['relations','关系图'],['search','知识检索'],['identity','身份整理'],['evolution','演化与治理'],['retirement','停用记录']] as const)" :key="tab[0]" type="button" :aria-current="(section ?? 'relations') === tab[0] ? 'page' : undefined" :disabled="mutationBusy" @click="emit('section',tab[0])">{{ tab[1] }}</button></nav>
      <div class="graph-actions"><button type="button" :disabled="mutationBusy" @click="emit('back')">返回资料</button><button type="button" :disabled="mutationBusy" @click="emit('demo')">演示图谱</button><button type="button" :disabled="loading || mutationBusy || neo4jSyncing" @click="emit('refresh')">刷新图谱</button></div>
    </header>
    <div v-show="!section || section === 'search'" ref="searchPane">
    <KnowledgeSearch :key="project?.id" :result="searchResult" :loading="searchLoading" :error="searchError" :error-action="searchErrorAction" :labels="labels"
      :rebuilding="searchRebuilding" :notice="searchNotice"
      :index-status="indexStatus" :index-status-loading="indexStatusLoading" :index-status-error="indexStatusError" @inspect-index="emit('inspectIndex')"
      :embedding-job="embeddingJob" :embedding-job-error="embeddingJobError"
      @search="(query, types, mode) => emit('search', query, types, mode)" @rebuild="retry => emit('rebuildSearch', retry)"
      @clear="emit('clearSearch')" @retry="emit('retrySearch')" @select="id => emit('selectSearchEntity', id)" @open-evidence="emit('openEvidence', $event)" />
    </div>
    <div class="formal-graph-deck" :class="{ 'relations-deck': !section || section === 'relations' }">
      <aside class="graph-controls" aria-label="筛选与时点">
        <div class="graph-pane-heading"><h2>筛选与时点</h2><p>类型、邻域、数据源</p></div>
        <div v-if="project && (!section || section === 'relations')" class="graph-source-bar">
          <label>图谱数据源 <select :value="backend ?? 'postgresql'" :disabled="mutationBusy || neo4jSyncing" @change="emit('backend', ($event.target as HTMLSelectElement).value as GraphBackend)">
            <option value="postgresql">PostgreSQL</option><option value="neo4j">Neo4j</option>
          </select></label>
          <template v-if="isNeo4j">
            <button class="graph-primary" type="button" :disabled="loading || mutationBusy || neo4jSyncing" @click="emit('syncNeo4j')">{{ neo4jSyncing ? '正在同步…' : '同步到 Neo4j' }}</button>
            <p v-if="neo4jSnapshot" class="graph-snapshot" role="status">
              快照时间 <time :datetime="neo4jSnapshot.valid_at">{{ new Date(neo4jSnapshot.valid_at).toLocaleString('zh-CN') }}</time>
              <span>共 {{ neo4jSnapshot.node_count }} 个节点、{{ neo4jSnapshot.edge_count }} 条关系</span>
            </p>
          </template>
        </div>
        <section v-if="project && !isNeo4j && (!section || section === 'relations')" class="graph-timeline" aria-label="图谱时间轴">
          <p v-if="timelineLoading" role="status">正在读取图谱时间轴…</p>
          <div v-else-if="timelineError" class="graph-error" role="alert">{{ timelineError }} <button type="button" @click="emit('retryTimeline')">重试时间轴</button></div>
          <template v-else-if="timeline?.instants.length">
            <div class="timeline-heading"><label for="graph-time-slider">图谱时间轴</label><output for="graph-time-slider">{{ sliderTime ? displayInstant(sliderTime) : '当前知识' }}</output></div>
            <input id="graph-time-slider" type="range" min="0" :max="stops.length" step="1" :value="sliderIndex"
              :disabled="mutationBusy" :aria-valuetext="sliderTime ? displayInstant(sliderTime) : '当前知识'"
              @input="previewIndex = ($event.target as HTMLInputElement).valueAsNumber" @change="selectTimeline" />
            <div class="timeline-limits"><time :datetime="stops[0]">{{ displayInstant(stops[0]!) }}</time><span>当前</span></div>
            <p v-if="timeline.truncated">时间轴仅列出最近的 200 个知识时点。可手动查询更早日期。</p>
          </template>
          <p v-else-if="timeline">确认知识后，时间轴会显示生效和失效时点。</p>
        </section>
        <div class="graph-toolbar">
          <form v-if="!isNeo4j" class="time-query" @submit.prevent="applyTime"><label>历史时间 <input v-model="localTime" type="datetime-local" step="0.001" :disabled="loading || mutationBusy" /></label><button type="submit" :disabled="loading || mutationBusy">查询该时刻</button><button v-if="validAt" type="button" :disabled="loading || mutationBusy" @click="emit('time', '')">返回当前知识</button></form>
          <span v-if="validAt && !isNeo4j" class="graph-kicker">历史视图 · {{ displayInstant(validAt) }}</span>
          <label>知识类型 <select :value="typeFilter" :disabled="loading || neo4jSyncing" @change="filter"><option value="">全部类型</option><option v-for="(label, type) in labels" :key="type" :value="type">{{ label }}</option></select></label>
          <label>邻域深度 <select :value="depth" :disabled="loading || neo4jSyncing || !center" @change="depthChange"><option value="1">一跳</option><option value="2">二跳</option></select></label>
          <button v-if="center" type="button" :disabled="loading || neo4jSyncing" @click="emit('reset')">返回项目总览</button>
        </div>
      </aside>
      <div class="graph-deck-content">
      <p v-if="isNeo4j && neo4jSyncError" class="graph-message graph-error" role="alert">{{ neo4jSyncError }}</p>
      <p v-if="loading" class="graph-message" role="status">正在读取已确认知识…</p>
      <div v-else-if="error" class="graph-message graph-error" role="alert"><p>{{ error }}</p><button type="button" :disabled="neo4jSyncing" @click="emit('refresh')">重试加载图谱</button></div>
      <div v-else-if="graph?.nodes.length === 0 && (!section || section === 'relations')" class="graph-empty"><span aria-hidden="true">◇</span><h2>这里还没有符合条件的知识</h2><p>在资料中提取并确认实体，再确认它们之间的关系。已确认的旧候选可点击“补写入图谱”。</p><button type="button" @click="emit('back')">前往资料审核</button></div>
      <div v-else-if="graph?.nodes.length" v-show="!section || section === 'relations'" class="graph-deck-results">
        <p v-if="graph.truncated" class="graph-message" role="status">当前只展示部分知识。可按类型筛选，或选择节点后查看它的一跳、二跳邻域。</p>
        <div class="real-graph-layout">
          <section class="real-graph-canvas" aria-label="已确认知识关系图">
            <div class="graph-pane-heading"><h2>关系视图</h2><p>选择节点或关系查看原文</p></div>
            <p v-if="hasEndedEdges" class="graph-scroll-hint ended-legend">虚线为该时点有效、后来失效或被替代的关系。</p>
            <p v-if="!labelsVisible" class="graph-scroll-hint" role="status">节点超过 50 个，已收起画布标签。可按类型筛选、缩小邻域或使用节点列表。</p>
            <div class="graph-scroll-area" tabindex="0" aria-label="图谱画布滚动区域">
              <svg :viewBox="`0 0 ${layout.width} ${layout.height}`" :style="{ aspectRatio: `${layout.width} / ${layout.height}` }" role="group" aria-label="真实项目知识图谱">
                <defs><marker id="real-graph-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="#9baabc" /></marker></defs>
                <g v-for="edge in graph.edges" :key="edge.id" class="real-edge" :class="{ selected: edge.id === selectedId, ended: ended(edge) }" role="button" tabindex="0" :aria-label="`查看关系：${edge.name}${ended(edge) ? '（后来失效）' : ''}`" @click="emit('selectRelationship', edge.id)" @keydown.enter="emit('selectRelationship', edge.id)" @keydown.space.prevent="emit('selectRelationship', edge.id)">
                  <path :d="edgePath(edge)" class="edge-hit" /><path :d="edgePath(edge)" marker-end="url(#real-graph-arrow)" />
                </g>
                <g v-for="node in positioned" :key="node.id" :transform="`translate(${node.x} ${node.y})`" class="real-node" :data-kind="node.type" :class="{ selected: selectedId === node.id }" role="button" tabindex="0" :aria-label="`查看知识：${node.name}`" @click="emit('selectEntity', node.id)" @keydown.enter="emit('selectEntity', node.id)" @keydown.space.prevent="emit('selectEntity', node.id)">
                  <title>{{ node.name }}</title>
                  <path v-if="node.type === 'Problem'" d="M-98 0 0 -34 98 0 0 34Z" />
                  <path v-else-if="node.type === 'Solution'" d="M-78 -34H78L98 0 78 34H-78L-98 0Z" />
                  <path v-else-if="node.type === 'Constraint'" d="M-72 -34H98L72 34H-98Z" />
                  <path v-else-if="node.type === 'CodeFile' || node.type === 'CodeEntity'" d="M-98 -34H76L98 -12V34H-98Z M76 -34V-12H98" />
                  <template v-else-if="node.type === 'Decision' || node.type === 'Technology' || node.type === 'Concept'">
                    <circle r="34" /><circle v-if="node.type === 'Decision'" r="26" />
                  </template>
                  <rect v-else x="-98" y="-34" width="196" height="68" rx="8" />
                  <template v-if="labelsVisible">
                    <text y="52" text-anchor="middle">{{ node.name.length > 15 ? node.name.slice(0, 15) + '…' : node.name }}</text>
                    <text y="68" text-anchor="middle" class="real-node-kind">{{ labels[node.type] ?? node.type }}</text>
                  </template>
                </g>
              </svg>
            </div>
            <ul class="formal-graph-legend" aria-label="当前图谱中的知识类型">
              <li v-for="kind in graphKinds" :key="kind" :data-kind="kind"><span aria-hidden="true"></span>{{ labels[kind] ?? kind }}</li>
            </ul>
            <details class="graph-records"><summary>节点与关系列表</summary><h2>知识节点</h2><button v-for="node in graph.nodes" :key="node.id" type="button" :aria-pressed="selectedId === node.id" @click="emit('selectEntity', node.id)">{{ node.name }} <small>{{ labels[node.type] ?? node.type }}</small></button><h2>知识关系</h2><p v-if="!graph.edges.length">尚无已确认关系。</p><button v-for="edge in graph.edges" :key="edge.id" type="button" :aria-pressed="selectedId === edge.id" @click="emit('selectRelationship', edge.id)">{{ edge.name }} <small>{{ edge.type }}</small></button></details>
            <div class="graph-status-bar" aria-label="图谱状态">
              <span class="graph-count">显示 <b>{{ graph.nodes.length }}</b> 个节点、<b>{{ graph.edges.length }}</b> 条关系</span>
              <span>邻域 {{ center ? `${depth} 跳` : '全图' }}</span>
              <span>时点 {{ validAt ? displayInstant(validAt) : '当前' }}</span>
              <span :class="{ 'labels-visible': labelsVisible }">{{ labelsVisible ? '标签显示中' : '标签已收起' }}</span>
            </div>
          </section>
          <aside id="formal-knowledge-detail" class="formal-detail" tabindex="-1" aria-label="正式知识与原文证据" :aria-busy="detailLoading">
            <div class="graph-pane-heading"><h2>知识详情</h2><p>概览、关系与证据</p></div>
            <p v-if="detailLoading" role="status">正在读取知识详情…</p>
            <div v-else-if="detailError" class="graph-error" role="alert"><p>{{ detailError }}</p><button type="button" @click="emit('retryDetail')">重试读取详情</button></div>
            <template v-else-if="selected">
              <span class="graph-kicker">{{ entityDetail ? '知识节点' : '知识关系' }} · {{ labels[selected.type] ?? selected.type }}</span><h2>{{ selected.name }}</h2><p class="formal-summary">{{ selected.summary }}</p>
              <dl><div><dt>确认状态</dt><dd>已确认</dd></div><div><dt>知识状态</dt><dd>{{ selected.status === 'superseded' ? '已被替代（历史有效）' : selected.status === 'active' ? '有效' : selected.status }}</dd></div><div><dt>模型置信度</dt><dd>{{ Math.round(selected.confidence * 100) }}%</dd></div><div><dt>有效起点</dt><dd>{{ new Date(selected.valid_from).toLocaleString('zh-CN') }}</dd></div><div v-if="selected.valid_to"><dt>有效截止</dt><dd>{{ new Date(selected.valid_to).toLocaleString('zh-CN') }}</dd></div></dl>
              <button v-if="entityDetail" class="graph-primary" type="button" :disabled="neo4jSyncing" @click="emit('neighborhood', selected.id)">以此知识为中心</button>
              <div v-if="relationshipDetail" class="graph-actions"><button type="button" :disabled="neo4jSyncing" @click="emit('neighborhood', relationshipDetail.relationship.source_id)">查看来源节点</button><button type="button" :disabled="neo4jSyncing" @click="emit('neighborhood', relationshipDetail.relationship.target_id)">查看目标节点</button></div>
              <h3>原文证据 <span>{{ evidence.length }}</span></h3>
              <p v-if="!evidence.length">暂无可访问的原文证据。</p>
              <article v-for="item in evidence" :key="item.id" class="formal-evidence"><strong>{{ item.title }}</strong><a v-if="item.git_url" :href="item.git_url" target="_blank" rel="noopener noreferrer">GitHub 原文 ↗</a><small>第 {{ item.start_line }}–{{ item.end_line }} 行 · {{ item.heading_path.join(' / ') || '文档开头' }}</small><blockquote>{{ item.quote }}</blockquote><button type="button" class="evidence-source-button" @click="emit('openEvidence', item)">查看原文分块</button></article>
              <template v-if="entityDetail"><h3>直接关系</h3><p v-if="!entityDetail.relationships.length">还没有已确认的直接关系。</p><button v-for="edge in entityDetail.relationships" :key="edge.id" type="button" class="formal-relation" @click="emit('selectRelationship', edge.id)">{{ edge.name }} <small>{{ edge.type }}</small></button><p v-if="entityDetail.truncated">仅展示前 100 条直接关系。</p></template>
            </template>
            <p v-else class="graph-detail-empty">在关系图中选择节点或连线，查看它的证据与有效期。</p>
          </aside>
        </div>
      </div>
      </div>
    </div>
    <label v-if="section && !['relations','search'].includes(section) && graph?.nodes.length" class="context-node-picker">当前知识<select :value="entityDetail?.entity.id ?? ''" :disabled="mutationBusy || detailLoading" @change="emit('selectEntity', ($event.target as HTMLSelectElement).value)"><option value="" disabled>选择要整理的知识</option><option v-for="node in graph.nodes" :key="node.id" :value="node.id">{{ node.name }}</option></select></label>
    <slot name="evolution" />
  </main>
</template>

<style scoped>
.graph-sections { display:flex;flex-wrap:wrap;gap:10px;margin-top:20px; }.graph-sections [aria-current=page] { background:var(--ink);color:white; }.context-node-picker { display:flex;gap:12px;align-items:center;font-size:13px; }.context-node-picker select { max-width:70%; }.route-error { color:var(--rose); }
.time-query { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }.time-query input { min-width: 0; max-width: 100%; min-height: 40px; padding: 6px; border: 1px solid #aabec0; border-radius: 5px; color: var(--ink); background: var(--paper); box-sizing: border-box; }.time-query input:focus-visible { outline: 2px solid var(--rose); outline-offset: 3px; }
.graph-timeline { padding: 8px 12px; min-width: 0; }
.timeline-heading, .timeline-limits { display: flex; justify-content: space-between; gap: 4px 16px; flex-wrap: wrap; }
.timeline-heading label { font-weight: 700; }
.timeline-limits, .graph-timeline p { font-size: 12px; color: #536b70; }
.graph-timeline input { width: 100%; margin: 5px 0; min-height: 24px; accent-color: var(--teal); cursor: pointer; }
.graph-timeline input:focus-visible { outline: 2px solid var(--rose); outline-offset: 3px; }
.real-edge.ended path:not(.edge-hit) { stroke-dasharray: 7 5; }
.ended-legend { padding-left: 10px; border-left: 2px dashed #718f94; }
.project-graph-page { height: calc(100% - 86px); overflow: auto; padding: 30px 30px 60px 100px; background: #edf3f3; color: var(--ink); }
.graph-page-heading { display: flex; justify-content: space-between; gap: 20px; align-items: center; }
.graph-kicker { color: var(--teal); font-size: 12px; }
h1 { margin: 9px 0; font: 500 32px "Noto Serif SC", SimSun, serif; overflow-wrap: anywhere; }
.graph-page-heading p, .graph-scroll-hint { color: #536b70; font-size: 12px; line-height: 1.8; }
button, select { min-height: 40px; padding: 8px 12px; border: 1px solid #aabec0; border-radius: 5px; color: var(--ink); background: var(--paper); cursor: pointer; font-size: 12px; }
button:disabled, select:disabled { opacity: .5; cursor: not-allowed; }
.graph-actions, .graph-toolbar, .graph-source-bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.graph-controls { margin: 22px 0; border: 1px solid var(--line); background: #f8fbfb; border-radius: 6px; font-size: 12px; }
.graph-toolbar, .graph-source-bar { padding: 12px 14px; }
.graph-source-bar { border-bottom: 1px solid var(--line); background: #eaf4f1; }
.graph-toolbar label, .graph-source-bar label { display: flex; align-items: center; gap: 8px; }
.graph-source-bar select:focus-visible, .graph-source-bar button:focus-visible { outline: 2px solid var(--rose); outline-offset: 3px; }
.graph-snapshot { display: flex; flex-wrap: wrap; gap: 4px 8px; margin: 0 0 0 auto; color: #385b5d; font-variant-numeric: tabular-nums; }
.graph-snapshot span { margin-inline-start: 4px; }
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
