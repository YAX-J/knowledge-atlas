<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import KnowledgeComparison from './KnowledgeComparison.vue'
import type { GovernanceKind } from '../types'
import type { EntityDetail, EvidenceLocator, FormalKnowledgeNode, GovernanceResult, KnowledgeChangeInput, KnowledgeChangeKind, KnowledgeChangeList, KnowledgeHistory } from '../types'

const props = defineProps<{
  nodes: FormalKnowledgeNode[]
  selected: EntityDetail | null
  history: KnowledgeHistory | null
  changes: KnowledgeChangeList | null
  governance: GovernanceResult | null
  historyLoading: boolean
  changesLoading: boolean
  governanceLoading: boolean
  historyError: string
  changesError: string
  governanceError: string
  actionError: string
  notice: string
  busy: boolean
  historical: boolean
  governanceKind?: GovernanceKind | ''
  comparison?: EntityDetail[] | null
  comparisonLoading?: boolean
  comparisonError?: string
}>()
const emit = defineEmits<{
  history: []
  changes: [page: number]
  inspect: [kind?: GovernanceKind | '']
  propose: [input: KnowledgeChangeInput]
  resolve: [id: string, action: 'confirm' | 'reject']
  openEvidence: [locator: EvidenceLocator]
  visitVersion: [id: string, at: string]
  openEntity: [id: string]
  compare: [ids: string[]]
  closeComparison: []
  retryComparison: []
}>()
const newId = ref('')
const kind = ref<KnowledgeChangeKind>('SUPERSEDES')
const reason = ref('')
const confirmed = ref('')
const labels: Record<KnowledgeChangeKind, string> = { SUPERSEDES: '替代', SUPPLEMENTS: '补充', CONFLICTS_WITH: '冲突' }
const statusLabels = { pending: '待审核', confirmed: '已确认', rejected: '已拒绝' }
const governanceLabels: Record<GovernanceKind, string> = { missing_evidence: '缺少证据', duplicate: '疑似重复', possible_conflict: '可能冲突', orphan: '孤立知识' }
function filterGovernance(event: Event) {
  emit('inspect', (event.target as HTMLSelectElement).value as GovernanceKind | '')
}
const eligible = computed(() => props.nodes.filter(item => item.id !== props.selected?.entity.id && item.type === props.selected?.entity.type && item.status === 'active' && !item.valid_to))
const names = computed(() => new Map([...(props.history?.entities ?? []), ...props.nodes].map(item => [item.id, item.name])))
function name(id: string) { return names.value.get(id) ?? id }
watch(() => props.selected?.entity.id, () => { newId.value = ''; reason.value = ''; confirmed.value = '' })
watch(() => props.changes, () => { confirmed.value = '' })
function submit() {
  if (!props.selected || !newId.value || !reason.value.trim() || !props.selected.evidence[0] || props.busy || props.historical) return
  emit('propose', { old_entity_id: props.selected.entity.id, new_entity_id: newId.value,
    evidence_id: props.selected.evidence[0].id, kind: kind.value, reason: reason.value.trim(), effective_at: new Date().toISOString() })
}
</script>

<template>
  <section class="evolution" aria-labelledby="evolution-title">
    <header><div><h2 id="evolution-title">知识演化与治理</h2><p>保留旧结论和原文。建议经人工确认后才生效。</p></div><button type="button" :disabled="busy || changesLoading" @click="emit('changes', changes?.page ?? 1)">刷新审核记录</button></header>
    <p v-if="notice" role="status" class="notice">{{ notice }}</p>
    <p v-if="actionError" role="alert" class="error">{{ actionError }}</p>
    <div class="evolution-columns">
      <section class="version-panel" aria-label="知识替代链">
        <h3>替代链</h3>
        <p v-if="!selected">选择一个正式知识节点，查看它的历史。</p>
        <p v-else-if="historyLoading" role="status">正在读取替代链…</p>
        <div v-else-if="historyError" role="alert" class="error">{{ historyError }} <button type="button" @click="emit('history')">重试历史</button></div>
        <template v-else-if="history">
          <p v-if="!history.changes.length">此知识尚无已确认替代记录。</p>
          <ol class="version-chain">
            <li v-for="entity in history.entities" :key="entity.id">
              <strong>{{ entity.name }}</strong><span>{{ entity.status === 'superseded' ? '已被替代' : entity.status === 'active' ? '有效' : entity.status }}</span>
              <p>{{ entity.summary }}</p><small>{{ new Date(entity.valid_from).toLocaleString('zh-CN') }} — {{ entity.valid_to ? new Date(entity.valid_to).toLocaleString('zh-CN') : '持续有效' }}</small>
              <button type="button" :disabled="busy" @click="emit('visitVersion', entity.id, entity.valid_from)">查看此版本与证据</button>
            </li>
          </ol>
          <article v-for="change in history.changes" :key="change.id" class="change-link"><strong>{{ change.new_entity_name }} → 替代 → {{ change.old_entity_name }}</strong><p>{{ change.reason }}</p><button v-for="item in change.evidence" :key="item.id" type="button" :disabled="busy" @click="emit('openEvidence', item)">核对替代证据：{{ item.title }} 第 {{ item.start_line }} 行</button></article>
          <p v-if="history.truncated" role="status">替代链超过 100 个实体或 200 条变更，仅展示部分历史。</p>
        </template>
      </section>
      <section aria-label="提出演化建议">
        <h3>提出演化建议</h3>
        <p v-if="historical">当前为历史视图。返回当前知识后才能提出或确认建议。</p>
        <p v-else-if="!selected">先选择需要比较的旧知识。</p>
        <p v-else-if="!eligible.length">当前画布中没有其他同类型有效实体。可清除类型/邻域筛选，或先确认另一份资料中的新结论。</p>
        <form v-else @submit.prevent="submit">
          <p>旧知识：<strong>{{ selected.entity.name }}</strong></p>
          <label>新知识<select v-model="newId" required :disabled="busy"><option value="">选择同类型的新知识</option><option v-for="node in eligible" :key="node.id" :value="node.id">{{ node.name }} — {{ node.summary }}</option></select></label>
          <label>关系<select v-model="kind" :disabled="busy"><option value="SUPERSEDES">新知识替代旧知识</option><option value="SUPPLEMENTS">新知识补充旧知识</option><option value="CONFLICTS_WITH">新旧知识存在冲突</option></select></label>
          <label>审核理由<textarea v-model="reason" required maxlength="2000" rows="3" :disabled="busy" placeholder="说明原文为何支持这项判断" /></label>
          <p>证据：{{ selected.evidence[0]?.title ?? '缺少证据，无法提出建议' }}。生效时间取提出建议时刻；替代确认后旧知识在此刻截止。</p>
          <button type="submit" :disabled="busy || !selected.evidence.length">保存待审核建议</button>
        </form>
      </section>
    </div>
    <section class="change-queue" aria-label="演化审核记录" :aria-busy="changesLoading">
      <h3>演化审核记录</h3><p v-if="changesLoading" role="status">正在读取审核记录…</p>
      <div v-else-if="changesError" role="alert" class="error">{{ changesError }} <button type="button" @click="emit('changes', changes?.page ?? 1)">重试审核记录</button></div>
      <p v-else-if="!changes?.items.length">尚无演化建议。检测不会自动创建或确认建议。</p>
      <div v-else class="queue-scroll" role="region" tabindex="0" aria-label="演化审核记录滚动区域">
        <article v-for="change in changes.items" :key="change.id">
          <strong>{{ change.new_entity_name }} → {{ labels[change.kind] }} → {{ change.old_entity_name }}</strong><span class="change-status">{{ statusLabels[change.review_status] }}</span>
          <p>{{ change.reason }}</p><small>生效时间 {{ new Date(change.effective_at).toLocaleString('zh-CN') }}</small>
          <blockquote v-for="item in change.evidence" :key="item.id">{{ item.quote }} <button type="button" :disabled="busy" @click="emit('openEvidence', item)">查看原文</button></blockquote>
          <template v-if="change.review_status === 'pending'">
            <template v-if="confirmed === change.id"><p>确认后不能撤回{{ change.kind === 'SUPERSEDES' ? '，旧知识将退出当前查询' : '，仅记录分类，不自动改写有效期' }}。原文是否支持该判断？</p><button type="button" :disabled="busy || historical" @click="emit('resolve', change.id, 'confirm')">确认此项{{ labels[change.kind] }}</button><button type="button" :disabled="busy" @click="confirmed = ''">取消确认</button></template>
            <button v-else type="button" :disabled="busy || historical" @click="confirmed = change.id">审核并确认</button>
            <button type="button" :disabled="busy || historical" @click="emit('resolve', change.id, 'reject')">拒绝建议</button>
          </template>
          <details v-else><summary>查看不可变审核快照</summary><pre>{{ JSON.stringify({ before: change.before, after: change.after }, null, 2) }}</pre></details>
        </article>
      </div>
      <nav v-if="changes && changes.total > changes.page_size" class="pagination" aria-label="演化记录分页"><button type="button" :disabled="busy || changesLoading || changes.page <= 1" @click="emit('changes', changes.page - 1)">上一页</button><span>第 {{ changes.page }} 页 / {{ changes.total }} 条</span><button type="button" :disabled="busy || changesLoading || changes.page * changes.page_size >= changes.total" @click="emit('changes', changes.page + 1)">下一页</button></nav>
    </section>
    <section class="governance" aria-label="知识质量检查">
      <h3 id="governance-title" tabindex="-1">知识质量检查 <button type="button" :disabled="busy || governanceLoading" @click="emit('inspect')">{{ governanceLoading ? '正在检查…' : '运行只读检查' }}</button></h3>
      <label>问题类别<select :value="governanceKind ?? ''" :disabled="busy || governanceLoading" @change="filterGovernance"><option value="">全部问题</option><option v-for="(label, value) in governanceLabels" :key="value" :value="value">{{ label }}</option></select></label>
      <p v-if="governance?.counts_by_kind">本次扫描范围：<span v-for="(label, value) in governanceLabels" :key="value">{{ label }} {{ governance.counts_by_kind[value] ?? 0 }}　</span></p>
      <p>检查当前知识的缺失证据、同名重复/可能冲突与孤立节点。结果只供人工核对，不会合并、删除或更改知识。</p>
      <div v-if="governanceError" role="alert" class="error">{{ governanceError }} <button type="button" @click="emit('inspect')">重试检查</button></div>
      <KnowledgeComparison :details="comparison ?? null" :loading="comparisonLoading ?? false" :error="comparisonError ?? ''" :busy="busy"
        @close="emit('closeComparison')" @retry="emit('retryComparison')" @open-evidence="emit('openEvidence', $event)" />
      <template v-if="governance"><p role="status">已扫描 {{ governance.scanned_entity_count }} 个当前实体；{{ governance.findings.length }} 条建议{{ governance.truncated ? '，已达扫描或结果上限' : '' }}。</p><p v-if="!governance.findings.length">本次有界检查未发现问题，不等同于完整语义质量保证。</p><ul class="findings"><li v-for="finding in governance.findings" :key="finding.id"><strong>{{ finding.entities?.map(item => item.name).join(' / ') || finding.entity_ids.map(name).join(' / ') }}</strong><p>{{ finding.message }}</p>
        <article v-for="entity in finding.entities ?? []" :key="entity.id" class="finding-entity"><p><strong>{{ entity.name }}</strong> · {{ entity.type }}</p><p>{{ entity.summary }}</p><button type="button" :disabled="busy" @click="emit('openEntity', entity.id)">核对知识与原文</button></article>
        <button v-if="finding.entity_ids.length === 2" type="button" :disabled="busy || comparisonLoading" @click="emit('compare', finding.entity_ids)">并排核对两条知识</button></li></ul></template>
    </section>
  </section>
</template>

<style scoped>
.evolution { margin-top: 28px; padding: 22px; border: 1px solid var(--line); background: var(--paper); border-radius: 7px; overflow-wrap: anywhere; }
header { display: flex; justify-content: space-between; align-items: start; gap: 20px; }h2 { font: 500 23px "Noto Serif SC", SimSun, serif; margin: 0; }h3 { font-size: 15px; margin: 12px 0; }p, small { color: #536b70; font-size: 12px; line-height: 1.9; }p { max-width: 75ch; }button, select, textarea { color: var(--ink); border: 1px solid #aabec0; border-radius: 5px; background: #f8fbfb; padding: 9px 12px; font: inherit; font-size: 12px; min-height: 40px; }button { cursor: pointer; margin: 4px 8px 4px 0; }button:disabled, select:disabled, textarea:disabled { opacity: .5; cursor: not-allowed; }button:focus-visible, select:focus-visible, textarea:focus-visible, [tabindex]:focus-visible, summary:focus-visible { outline: 2px solid var(--rose); outline-offset: 3px; }.evolution-columns { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 28px; margin: 20px 0; }.evolution-columns > section { min-width: 0; }label { display: grid; gap: 7px; margin: 12px 0; font-size: 12px; }select, textarea { width: 100%; min-width: 0; box-sizing: border-box; }textarea { resize: vertical; }.version-chain { padding: 0 0 0 20px; border-left: 2px solid #a3b9b7; list-style: none; }.version-chain li { position: relative; padding: 0 0 24px 0; }.version-chain li::before { content: ''; width: 8px; height: 8px; position: absolute; left: -25px; top: 5px; border-radius: 50%; background: var(--rose); }.version-chain span { margin-left: 12px; font-size: 11px; color: var(--rose); }.version-chain small { display: block; }.version-chain p { margin: 6px 0; }.change-link { border-top: 1px solid var(--line); padding: 12px 0; font-size: 12px; }.change-queue, .governance { border-top: 1px solid var(--line); padding-top: 15px; margin-top: 20px; }.queue-scroll, .findings { max-height: 420px; overflow: auto; }.queue-scroll article { border-bottom: 1px solid var(--line); padding: 16px 0; font-size: 13px; }.change-status { display: inline-block; margin: 6px 12px; color: var(--rose); font-size: 12px; }blockquote { margin: 12px 0; padding: 10px 14px; border-left: 2px solid #a3b9b7; white-space: pre-wrap; font-size: 12px; }pre { max-height: 260px; overflow: auto; font-size: 11px; white-space: pre-wrap; }summary { cursor: pointer; font-size: 12px; margin: 12px 0; }.findings { padding-left: 20px; }.findings li { padding: 8px 0; font-size: 12px; }.pagination { display: flex; align-items: center; gap: 12px; font-size: 12px; }.error { color: #91274d; }.notice { color: #245c4e; padding: 12px; background: #dceee7; }
@media (max-width: 1000px) { .evolution-columns { grid-template-columns: minmax(0, 1fr); }header { flex-wrap: wrap; } }
</style>
