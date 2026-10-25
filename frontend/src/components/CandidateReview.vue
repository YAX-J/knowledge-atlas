<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { CandidateList, ExtractionResult } from '../api/knowledgeAtlas'
import type { KnowledgeCandidate, ReviewDecision } from '../types'

const props = defineProps<{
  candidates: CandidateList | null
  extraction: ExtractionResult | null
  loading: boolean
  extracting: boolean
  resolving: string
  error: string
  notice: string
}>()
const emit = defineEmits<{
  extract: []
  refresh: [page?: number]
  resolve: [decision: ReviewDecision]
  graph: []
  resolveBatch: [ids: string[], action: 'confirm' | 'reject']
}>()
const editing = ref('')
const name = ref('')
const summary = ref('')
const pages = computed(() => Math.max(1, Math.ceil((props.candidates?.total ?? 0) / (props.candidates?.page_size ?? 20))))
const busy = computed(() => props.extracting || !!props.resolving)
const selected = ref<string[]>([])
const batchAction = ref<'confirm' | 'reject' | ''>('')
const pending = computed(() => props.candidates?.items.filter(item => item.review_status === 'pending') ?? [])
const batchDisabled = computed(() => busy.value || props.loading || !!editing.value)
watch(() => props.candidates, () => {
  selected.value = selected.value.filter(id => pending.value.some(item => item.id === id))
  if (!pending.value.some(item => item.id === editing.value)) editing.value = ''
  batchAction.value = ''
})
watch(selected, () => { batchAction.value = '' }, { deep: true })
function selectPage() {
  if (batchDisabled.value) return
  selected.value = pending.value.map(item => item.id)
}
function submitBatch() {
  if (batchDisabled.value || !batchAction.value || !selected.value.length) return
  emit('resolveBatch', [...selected.value], batchAction.value)
}
const counts = computed(() => props.extraction?.review_counts)
const nextStep = computed(() => {
  if (props.loading) return '正在读取整份资料的处理进度。'
  if (props.error) return '状态读取或处理失败，请刷新候选并核对错误信息。'
  if (props.extracting || props.extraction?.task?.status === 'running') return '正在抽取候选，请等待完成或刷新状态。'
  if (props.extraction?.task?.status !== 'succeeded') return '资料已解析；下一步提取候选。尚未确认的内容不会进入知识问答。'
  if (!props.extraction.candidate_count) return '抽取完成，但没有候选知识；请核对资料是否包含明确的技术结论。'
  if (counts.value?.pending) return '下一步核对并审核候选，先确认实体，再确认关系。'
  if (counts.value?.confirmed) return '审核已完成，可查看项目图谱；使用语义检索前请显式更新索引。'
  if (counts.value) return '候选均已拒绝，本篇资料没有通过审核的知识。'
  return '抽取完成，请刷新候选查看整份资料的审核进度。'
})
const labels: Record<string, string> = {
  pending: '待确认', confirmed: '已确认', rejected: '已拒绝',
  Project: '项目', CodeFile: '代码文件', CodeEntity: '代码实体', Technology: '技术',
  Concept: '概念', Problem: '问题', Solution: '方案', Decision: '决策',
  Alternative: '候选方案', Constraint: '约束',
  BELONGS_TO: '归属', CONTAINS: '包含', DEPENDS_ON: '依赖', CALLS: '调用', USES: '使用',
  SOLVES: '解决', CAUSED_BY: '原因', AFFECTS: '影响', DECIDED_IN: '决策依据',
  CHOSEN_OVER: '方案比较', CONSTRAINED_BY: '受约束', IMPLEMENTED_BY: '实现',
  EVIDENCED_BY: '证据', EXTRACTED_FROM: '来源', LEARNED_FROM: '经验', SUPERSEDES: '替代',
}
async function edit(item: KnowledgeCandidate) {
  editing.value = item.id
  name.value = item.name
  summary.value = item.summary
  await nextTick()
  document.getElementById(`candidate-name-${item.id}`)?.focus()
}
watch(() => props.resolving, async (current, previous) => {
  if (!current && previous && props.candidates?.items.some(item => item.id === previous && item.review_status !== 'pending')) {
    await nextTick()
    document.getElementById(`candidate-${previous}`)?.focus({ preventScroll: true })
  }
})
function confirm(id: string) {
  if (busy.value || props.loading) return
  emit('resolve', { id, action: 'confirm', changes: { name: name.value.trim(), summary: summary.value.trim() } })
}
</script>

<template>
  <section class="candidate-review" aria-labelledby="candidate-title" :aria-busy="loading || busy">
    <div class="source-section-heading">
      <h3 id="candidate-title">候选知识 <span v-if="candidates">{{ candidates.total }}</span></h3>
      <button class="text-button" type="button" :disabled="loading || busy" @click="emit('refresh')">刷新候选</button>
    </div>
    <p class="source-upload-hint">提取时会将本篇资料的原文分块发送至 DeepSeek。核对证据并确认后，知识会写入项目图谱；关系两端的实体需要先确认。</p>
    <div class="review-progress" role="status">
      <strong>资料处理进度</strong><p>{{ nextStep }}</p>
      <p v-if="counts && !loading && !error">整份资料：待审核 {{ counts.pending }} · 已确认 {{ counts.confirmed }} · 已拒绝 {{ counts.rejected }}</p>
      <button v-if="counts?.confirmed" class="text-button" type="button" :disabled="loading || busy" @click="emit('graph')">查看图谱与检索</button>
    </div>
    <button v-if="extraction?.task?.status !== 'succeeded'" class="primary-button" type="button" :disabled="loading || busy" @click="emit('extract')">
      {{ extracting ? '正在提取，请稍候…' : extraction?.task?.status === 'failed' ? '重试提取候选知识' : extraction?.task?.status === 'running' ? '恢复超时提取' : '提取候选知识' }}
    </button>
    <p v-if="extraction?.task?.status === 'running' && !extracting" class="muted-copy" role="status">提取任务正在执行，请刷新候选查看结果。中断后可在租约到期时手动恢复。</p>
    <p v-if="loading" class="muted-copy" role="status">正在读取候选知识…</p>
    <p v-if="error" class="inline-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="success-copy" role="status">{{ notice }}</p>
    <section v-if="pending.length" class="batch-review" aria-label="批量审核">
      <p>已选 {{ selected.length }} 条当前页候选。请逐项核对原文后选择；关系两端须已确认或一同选中。</p>
      <p v-if="editing" class="muted-copy">请先完成或取消正在修改的候选。</p>
      <div class="candidate-actions">
        <button class="text-button" type="button" :disabled="batchDisabled" @click="selectPage">选择本页待审核项</button>
        <button class="text-button" type="button" :disabled="batchDisabled || !selected.length" @click="selected = []">清空选择</button>
        <button class="primary-button" type="button" :disabled="batchDisabled || !selected.length" @click="batchAction = 'confirm'">审核所选</button>
        <button class="text-button" type="button" :disabled="batchDisabled || !selected.length" @click="batchAction = 'reject'">拒绝所选</button>
      </div>
      <form v-if="batchAction" class="batch-preview" @submit.prevent="submitBatch">
        <p>将{{ batchAction === 'confirm' ? '确认并写入图谱' : '拒绝' }}以下 {{ selected.length }} 条候选：</p>
        <ul><li v-for="item in pending.filter(item => selected.includes(item.id))" :key="item.id">{{ item.kind === 'entity' ? '实体' : '关系' }}：{{ item.name }}</li></ul>
        <p>任意一项无法处理时整批不生效。处理后暂不支持撤销。</p>
        <button class="primary-button" type="submit" :disabled="batchDisabled">{{ batchAction === 'confirm' ? '确认所选并入图' : '确认拒绝所选' }}</button>
        <button class="text-button" type="button" :disabled="batchDisabled" @click="batchAction = ''">取消批量操作</button>
      </form>
    </section>
    <p v-if="!loading && !error && candidates?.total === 0" class="empty-copy">{{ extraction?.task?.status === 'succeeded' ? '本篇资料未提取到有明确证据的候选知识。' : '还没有候选知识。完成提取后，可在这里核对名称、摘要和原文证据。' }}</p>
    <article v-for="item in candidates?.items ?? []" :key="item.id" class="candidate-card">
      <header>
        <label v-if="item.review_status === 'pending'" class="candidate-select"><input v-model="selected" type="checkbox" :value="item.id" :disabled="batchDisabled" :aria-label="`选择候选：${item.name}`" />选择</label>
        <span>{{ item.kind === 'entity' ? '实体' : '关系' }} · {{ labels[item.type] ?? item.type }}</span>
        <span class="source-status" :class="{ 'status-ready': item.review_status === 'confirmed', 'status-failed': item.review_status === 'rejected' }">{{ labels[item.review_status] }}</span>
      </header>
      <h4 :id="`candidate-${item.id}`" tabindex="-1">{{ item.name }}</h4>
      <p class="candidate-summary">{{ item.summary }}</p>
      <small class="muted-copy">模型置信度 {{ Math.round(item.confidence * 100) }}% · 请以原文证据为准</small>
      <blockquote v-for="(evidence, index) in item.evidence" :key="index">
        <cite>原文第 {{ evidence.start_line }}–{{ evidence.end_line }} 行 · {{ evidence.heading_path.join(' / ') || '文档开头' }}</cite>
        <p>{{ evidence.quote }}</p>
      </blockquote>
      <template v-if="item.review_status === 'pending'">
        <form v-if="editing === item.id" class="project-form" @submit.prevent="confirm(item.id)">
          <label :for="`candidate-name-${item.id}`">名称</label>
          <input :id="`candidate-name-${item.id}`" v-model="name" required maxlength="255" :disabled="busy" />
          <label :for="`candidate-summary-${item.id}`">摘要</label>
          <textarea :id="`candidate-summary-${item.id}`" v-model="summary" required maxlength="2000" rows="3" :disabled="busy" />
          <div class="candidate-actions">
            <button class="primary-button" type="submit" :disabled="busy || !name.trim() || !summary.trim()">保存并确认</button>
            <button class="text-button" type="button" :disabled="busy" @click="editing = ''">取消修改</button>
          </div>
        </form>
        <div v-else class="candidate-actions">
          <button class="primary-button" type="button" :disabled="busy || loading" @click="emit('resolve', { id: item.id, action: 'confirm' })">{{ resolving === item.id ? '正在处理…' : '确认' }}</button>
          <button class="text-button" type="button" :disabled="busy || loading" @click="edit(item)">修改后确认</button>
          <button class="text-button" type="button" :disabled="busy || loading" @click="emit('resolve', { id: item.id, action: 'reject' })">拒绝</button>
        </div>
        <p v-if="item.kind === 'relation'" class="muted-copy">请先确认关系两端的实体。</p>
      </template>
      <div v-else-if="item.review_status === 'confirmed' && !item.knowledge_id" class="candidate-actions">
        <span class="muted-copy">这条旧候选已通过审核，尚未写入正式图谱。</span>
        <button class="primary-button" type="button" :disabled="busy || loading" @click="emit('resolve', { id: item.id, action: 'confirm' })">补写入图谱</button>
      </div>
    </article>
    <nav v-if="pages > 1" class="source-pagination" aria-label="候选知识分页">
      <button type="button" :disabled="loading || busy || (candidates?.page ?? 1) <= 1" @click="emit('refresh', (candidates?.page ?? 1) - 1)">上一页</button>
      <span>{{ candidates?.page }} / {{ pages }}</span>
      <button type="button" :disabled="loading || busy || (candidates?.page ?? 1) >= pages" @click="emit('refresh', (candidates?.page ?? 1) + 1)">下一页</button>
    </nav>
  </section>
</template>

<style scoped>
.batch-review { margin: 16px 0; padding: 14px; border: 1px solid var(--line); border-radius: 6px; font-size: 12px; line-height: 1.8; }
.batch-preview { margin-top: 14px; border-top: 1px solid var(--line); padding-top: 12px; }
.batch-preview ul { max-height: 180px; overflow: auto; overflow-wrap: anywhere; }
.candidate-select { display: flex; align-items: center; gap: 6px; }
.candidate-select input { width: 18px; height: 18px; }
.review-progress { margin: 14px 0; padding: 12px; border-left: 3px solid var(--teal); background: #edf5f3; font-size: 12px; line-height: 1.8; }
.candidate-review { margin-top: 30px; padding-top: 24px; border-top: 1px solid var(--line); }
.candidate-card { margin-top: 16px; padding: 18px; border: 1px solid var(--line); border-radius: 6px; background: #f7faf9; }
.candidate-card header { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: var(--teal); font-size: 12px; }
.candidate-card h4 { margin: 15px 0 8px; font-size: 16px; line-height: 1.6; overflow-wrap: anywhere; }
.candidate-summary { margin: 8px 0; font-size: 13px; line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; }
.candidate-card blockquote { margin: 14px 0; padding: 12px 14px; border-left: 3px solid #a2b9b7; background: #eaf1ef; }
.candidate-card cite { color: var(--muted); font-size: 11px; font-style: normal; overflow-wrap: anywhere; }
.candidate-card blockquote p { margin: 8px 0 0; font-size: 12px; line-height: 1.9; white-space: pre-wrap; overflow-wrap: anywhere; }
.candidate-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 14px; }
.candidate-card .project-form { margin-top: 12px; }
@media (max-width: 760px) {
  .candidate-card { padding: 14px 12px; }
  .candidate-card blockquote { padding: 10px; }
}
</style>
