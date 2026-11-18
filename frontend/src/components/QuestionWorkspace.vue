<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ApiProject, ApiProjectList } from '../api/knowledgeAtlas'
import type { EvidenceLocator, QuestionAnswer, QuestionRetrievalMode } from '../types'
import AnswerClaims from './AnswerClaims.vue'

const props = defineProps<{
  projects: ApiProjectList | null
  project: ApiProject | null
  projectsLoading: boolean
  projectsError: string
  result: QuestionAnswer | null
  loading: boolean
  error: string
  persistent?: boolean
}>()
const emit = defineEmits<{
  selectProject: [project: ApiProject]
  retryProjects: []
  ask: [question: string, mode: QuestionRetrievalMode, validAt?: string]
  retry: []
  clear: []
  openEntity: [id: string]
  openEvidence: [locator: EvidenceLocator]
}>()
const question = ref('')
const mode = ref<QuestionRetrievalMode>('rrf')
const retrievalLabels: Record<QuestionRetrievalMode, string> = {
  hybrid: '混合 + 图关系', rrf: 'BM25 + 向量融合', vector: '语义向量',
  bm25: 'BM25', bm25_source: 'BM25 + 来源位置',
}
const historyTime = ref('')
const timeInput = ref<HTMLInputElement | null>(null)
const validAt = computed(() => {
  if (!historyTime.value) return ''
  const date = new Date(historyTime.value)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
})
const remaining = computed(() => 200 - question.value.length)
const coverage = computed(() => {
  const result = props.result
  if (['bm25', 'bm25_source'].includes(result?.retrieval.mode ?? '')) return '无需索引'
  if (!result?.retrieval.eligible_count) return '0%'
  return `${Math.round(result.retrieval.indexed_count / result.retrieval.eligible_count * 100)}%`
})

watch(() => props.project?.id, () => { question.value = ''; historyTime.value = '' })

function selectProject(event: Event) {
  const id = (event.target as HTMLSelectElement).value
  const selected = props.projects?.items.find(item => item.id === id)
  if (selected) emit('selectProject', selected)
}
function submit() {
  const value = question.value.trim()
  if (!value || value.length > 200 || !props.project || props.loading || validAt.value === null) return
  if (validAt.value) emit('ask', value, mode.value, validAt.value)
  else emit('ask', value, mode.value)
}
function adjustTime() {
  const result = props.result
  if (!result) return
  question.value = result.question
  if (result.time_scope?.valid_at) {
    const date = new Date(result.time_scope.valid_at)
    historyTime.value = new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 19)
  }
  timeInput.value?.focus()
}
</script>

<template>
  <component :is="persistent ? 'section' : 'main'" class="question-page" aria-labelledby="question-title">
    <header class="question-heading">
      <div>
        <span class="question-kicker">项目知识 / 可核验回答</span>
        <h1 id="question-title">向证据提问</h1>
        <p>回答只使用项目中已确认的原文证据；证据不足时会明确拒答。</p>
      </div>
      <label class="project-picker">
        当前项目
        <select :value="project?.id ?? ''" :disabled="loading || projectsLoading" @change="selectProject">
          <option value="" disabled>请选择项目</option>
          <option v-for="item in projects?.items ?? []" :key="item.id" :value="item.id">{{ item.name }}</option>
        </select>
      </label>
    </header>

    <div class="question-results">
      <section v-if="!project && projectsLoading" class="question-state" role="status">
        <span class="pulse" aria-hidden="true">◎</span><h2>正在读取项目</h2><p>项目加载完成后即可限定问答范围。</p>
      </section>
      <section v-else-if="!project && projectsError" class="question-state error-state" role="alert">
        <span aria-hidden="true">!</span><h2>项目列表加载失败</h2><p>{{ projectsError }}</p><button type="button" @click="emit('retryProjects')">重试加载项目</button>
      </section>
      <section v-else-if="!project" class="question-state">
        <span aria-hidden="true">◇</span><h2>先选择一个项目</h2><p>问答范围严格限定在当前项目的已确认知识中。</p>
      </section>
      <section v-else-if="loading" class="question-state" role="status" aria-live="polite">
        <span class="pulse" aria-hidden="true">◎</span><h2>正在检索项目证据</h2><p>正在核对已确认知识及原文。停止等待不会撤销服务端已发出的模型请求。</p>
      </section>
      <section v-else-if="error" class="question-state error-state" role="alert">
        <span aria-hidden="true">!</span><h2>这次没有得到可确认的结果</h2><p>{{ error }}</p><button type="button" @click="emit('retry')">重试本次问题</button>
      </section>
      <section v-else-if="result" class="answer-layout">
        <section v-if="result.time_scope?.source !== 'comparison'" class="question-retrieval" aria-label="提问原文与检索统计">
          <div class="question-quote">
            <h2>提问原文</h2>
            <p>{{ result.question }}</p>
            <small>{{ result.time_scope?.valid_at ? new Date(result.time_scope.valid_at).toLocaleString('zh-CN') : '未限定时点' }}</small>
          </div>
          <div class="question-retrieval-summary">
            <div><h2>检索组成</h2><span>后端计算</span></div>
            <p v-if="result.retrieval.mode">{{ retrievalLabels[result.retrieval.mode] }}</p>
            <dl class="retrieval-stats">
              <div><dt>关键词命中</dt><dd>{{ result.retrieval.keyword_hits }}</dd></div>
              <div v-if="result.retrieval.bm25_hits != null"><dt>BM25 命中</dt><dd>{{ result.retrieval.bm25_hits }}</dd></div>
              <div><dt>语义命中</dt><dd>{{ result.retrieval.vector_hits }}</dd></div>
              <div><dt>图关系命中</dt><dd>{{ result.retrieval.graph_hits }}</dd></div>
              <div><dt>语义索引覆盖</dt><dd>{{ coverage }}</dd></div>
            </dl>
            <p class="retrieval-hint">本次选取 {{ result.retrieval.unique_evidence_count ?? result.evidence.length }} 段去重原文，去除 {{ result.retrieval.duplicate_evidence_count ?? 0 }} 次重复引用。<span v-if="result.retrieval.truncated">本次使用有界检索结果，未覆盖项目全部知识。</span></p>
          </div>
        </section>
        <article class="answer-card">
          <div class="answer-status" :class="{ unsupported: !result.supported }">
            <span>{{ result.supported ? '附有引用' : result.claims?.some(claim => claim.status === 'supported') ? '部分结论有引用' : '证据不足' }}</span>
            <strong v-if="result.time_scope?.source !== 'comparison'">{{ Math.round(result.confidence * 100) }}% 置信度</strong>
          </div>
          <p v-if="result.time_scope?.source === 'comparison'" class="asked">{{ result.question }}</p>
          <h2>{{ result.time_scope?.source === 'comparison' ? '切换前后对比' : result.time_scope?.source === 'clarification' ? '请选择查询时点' : result.supported ? '回答' : result.claims?.some(claim => claim.status === 'supported') ? '回答与待确认事项' : '暂不能确认' }}</h2>
          <AnswerClaims :answer="result" @open-evidence="emit('openEvidence', $event)" />
          <button v-if="result.time_scope && result.time_scope.source !== 'comparison'" type="button" @click="adjustTime">{{ result.time_scope.source === 'clarification' ? '手动选择时点' : '修改查询时点' }}</button>
          <template v-if="result.missing_information.length">
            <h3>仍需补充</h3>
            <ul><li v-for="item in result.missing_information" :key="item">{{ item }}</li></ul>
          </template>

        </article>

        <aside class="evidence-panel" aria-label="回答引用的原文证据">
          <div class="evidence-heading"><span>引用证据</span><strong>{{ result.evidence.length }}</strong></div>
          <p v-if="!result.evidence.length" class="no-evidence">本次没有可引用的证据。</p>
          <article v-for="(item, index) in result.evidence" :key="item.id" class="evidence-card">
            <div><span>[{{ index + 1 }}]</span><button type="button" @click="emit('openEntity', item.entity_id)">{{ item.entity_name }} ↗</button></div>
            <p v-if="(item.related_entities?.length ?? 0) > 1" class="related-evidence-entities">同一原文也关联：<button v-for="entity in item.related_entities?.filter(entity => entity.id !== item.entity_id) ?? []" :key="entity.id" type="button" @click="emit('openEntity', entity.id)">{{ entity.name }} ↗</button></p>
            <strong>{{ item.title }}</strong>
            <small>第 {{ item.start_line }}–{{ item.end_line }} 行 · {{ item.heading_path.join(' / ') || '文档开头' }}</small>
            <a v-if="item.git_url" :href="item.git_url" target="_blank" rel="noopener noreferrer">在 GitHub 查看来源 ↗</a>
            <blockquote>{{ item.quote }}</blockquote>
            <button type="button" class="evidence-source-button" @click="emit('openEvidence', item)">查看原文分块</button>
          </article>
        </aside>
      </section>
      <section v-else class="question-state">
        <span aria-hidden="true">?</span><h2>提出一个问题</h2><p>回答与引用会显示在这里。打开引用即可核对文件、行号和原文。</p>
      </section>
    </div>
    <section class="ask-card" aria-label="提问">
      <form @submit.prevent="submit">
        <label for="evidence-question">你想从项目知识中确认什么？</label>
        <textarea id="evidence-question" v-model="question" maxlength="200" rows="4"
          :disabled="loading || !project" placeholder="例如：项目为什么选择 PostgreSQL，而没有采用其他方案？" />
        <label for="question-retrieval-mode">证据检索方式</label>
        <select id="question-retrieval-mode" v-model="mode" :disabled="loading">
          <option value="hybrid">混合 + 图关系</option><option value="rrf">BM25 + 向量融合</option>
          <option value="vector">语义向量</option><option value="bm25">BM25 · 检索无需嵌入</option><option value="bm25_source">BM25 + 来源位置</option>
        </select>
        <label for="question-valid-at">知识时点（留空时从问题识别）</label>
        <input id="question-valid-at" ref="timeInput" v-model="historyTime" type="datetime-local" step="1" :disabled="loading || !project" />
        <p v-if="validAt === null" class="retrieval-hint" role="alert">请输入有效的查询日期和时间。</p>
        <details class="ask-help">
          <summary>检索方式和时点说明</summary>
          <p class="retrieval-hint">对比两天请留空知识时点，例如「对比 2026-04-01 和 2026-06-01，订单服务的主数据库有什么变化？」</p>
          <p class="retrieval-hint">普通问答使用模型生成回答。BM25 可直接检索已确认知识，向量相关方式需要配置嵌入服务并更新索引。</p>
        </details>
        <div class="ask-footer">
          <small>{{ remaining }} 字可用 · {{ persistent ? '回答和证据将保存在当前项目会话' : '当前回答不会保存为历史记录' }}</small>
          <div>
            <button v-if="result || error || loading" type="button" @click="emit('clear')">{{ loading ? '停止等待' : '清除回答' }}</button>
            <button class="primary" type="submit" :disabled="loading || !project || !question.trim() || validAt === null">
              {{ loading ? '正在检索证据…' : '检索并回答' }}
            </button>
          </div>
        </div>
      </form>
    </section>
  </component>
</template>

<style scoped>
.related-evidence-entities { font-size: 12px; line-height: 1.8; color: #435e64; }
.retrieval-hint { font-size: 12px; line-height: 1.8; color: #536b70; }
#question-retrieval-mode { max-width: 100%; padding: 8px; margin-top: 8px; }
#question-valid-at { max-width: 100%; min-height: 40px; padding: 8px; border: 1px solid #aabec0; border-radius: 5px; background: var(--paper); color: var(--ink); font: inherit; }
#question-valid-at:focus-visible { outline: 2px solid var(--teal); outline-offset: 2px; }
.ask-card label[for="question-valid-at"] { margin-top: 12px; }
.question-page { height: calc(100% - 86px); overflow: auto; padding: 34px 42px 70px 112px; background: #edf3f3; color: var(--ink); }
.question-heading { display: flex; justify-content: space-between; align-items: end; gap: 28px; max-width: 1180px; margin: 0 auto; }
.question-kicker { color: var(--teal); font-size: 12px; letter-spacing: .08em; }
h1 { margin: 9px 0; font: 500 34px "Noto Serif SC", SimSun, serif; }
.question-heading p { margin: 0; color: #536b70; font-size: 13px; line-height: 1.8; }
.project-picker { display: grid; gap: 7px; min-width: 230px; font-size: 11px; color: #536b70; }
select, button, textarea { font: inherit; color: var(--ink); }
select, button { min-height: 40px; padding: 8px 12px; border: 1px solid #aabec0; border-radius: 5px; background: var(--paper); }
button { cursor: pointer; } button:disabled, select:disabled, textarea:disabled { opacity: .55; cursor: not-allowed; }
.ask-card { max-width: 1180px; margin: 28px auto 22px; padding: 22px; border: 1px solid var(--line); border-radius: 7px; background: #f9fbfb; box-shadow: 0 12px 35px rgba(37, 66, 68, .06); }
.ask-card label { display: block; margin-bottom: 10px; font-size: 13px; font-weight: 600; }
textarea { box-sizing: border-box; width: 100%; padding: 14px; resize: vertical; border: 1px solid #aabec0; border-radius: 5px; background: #fff; line-height: 1.8; }
textarea:focus-visible, button:focus-visible, select:focus-visible { outline: 2px solid var(--teal); outline-offset: 2px; }
.ask-footer, .ask-footer > div { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.ask-footer { margin-top: 12px; }.ask-footer small { color: #63797d; }.primary { color: white; border-color: var(--ink); background: var(--ink); }
.question-state { display: grid; justify-items: center; max-width: 1180px; margin: 0 auto; padding: 72px 20px; border: 1px solid var(--line); background: rgba(249, 251, 251, .8); text-align: center; }
.question-state > span { display: grid; place-items: center; width: 54px; height: 54px; border: 1px solid #91afb2; border-radius: 50%; color: var(--teal); font: 24px Georgia, serif; }
.question-state h2 { margin: 18px 0 5px; font: 500 20px "Noto Serif SC", SimSun, serif; }.question-state p { max-width: 560px; color: #536b70; font-size: 13px; line-height: 1.9; }
.error-state > span { border-color: #b86782; color: #91274d; }.error-state p { color: #7b3850; overflow-wrap: anywhere; }
.pulse { animation: pulse 1.4s ease-in-out infinite; } @keyframes pulse { 50% { transform: scale(.88); opacity: .55; } }
.answer-layout { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(310px, .65fr); gap: 20px; max-width: 1180px; margin: 0 auto; align-items: start; }
.answer-card, .evidence-panel { min-width: 0; padding: 24px; border: 1px solid var(--line); border-radius: 7px; background: #f9fbfb; }
.answer-status { display: flex; justify-content: space-between; gap: 16px; padding-bottom: 16px; border-bottom: 1px solid var(--line); color: #245c4e; font-size: 12px; }.answer-status span { padding: 5px 9px; border-radius: 4px; background: #dceee7; }.answer-status.unsupported { color: #8a5a21; }.answer-status.unsupported span { background: #f2e8d5; }
.asked { margin: 20px 0; padding-left: 12px; border-left: 2px solid #a3b9b7; color: #536b70; font-size: 12px; line-height: 1.8; overflow-wrap: anywhere; }
.answer-card h2 { font: 500 21px "Noto Serif SC", SimSun, serif; }.answer-card h3 { margin-top: 28px; font-size: 13px; }.answer-text { white-space: pre-wrap; overflow-wrap: anywhere; font-size: 14px; line-height: 2; }.answer-card li { margin: 8px 0; font-size: 13px; line-height: 1.7; }
.retrieval-stats { display: grid; grid-template-columns: repeat(4, 1fr); margin: 30px 0 0; border-top: 1px solid var(--line); }.retrieval-stats div { padding: 16px 7px 0; border-right: 1px solid var(--line); text-align: center; }.retrieval-stats div:last-child { border: 0; }.retrieval-stats dt { color: #63797d; font-size: 10px; }.retrieval-stats dd { margin: 8px 0 0; font-size: 17px; }
.evidence-heading { display: flex; justify-content: space-between; padding-bottom: 15px; border-bottom: 1px solid var(--line); font-size: 13px; }.evidence-heading strong { color: var(--teal); }.no-evidence { color: #63797d; font-size: 12px; }
.evidence-card { margin-top: 16px; padding: 14px; border: 1px solid var(--line); border-radius: 5px; background: #fff; overflow-wrap: anywhere; }.evidence-card > div { display: flex; align-items: center; gap: 8px; margin-bottom: 9px; color: var(--teal); font-size: 11px; }.evidence-card button { min-height: 30px; padding: 4px 8px; border: 0; color: var(--teal); background: transparent; text-decoration: underline; }.evidence-card strong, .evidence-card small { display: block; }.evidence-card small { margin-top: 6px; color: #63797d; font-size: 10px; line-height: 1.6; }.evidence-card > a { display: inline-block; margin-top: 8px; color: var(--teal); font-size: 11px; }.evidence-card blockquote { margin: 12px 0 0; padding-left: 10px; border-left: 2px solid #a3b9b7; white-space: pre-wrap; font-size: 12px; line-height: 1.85; }
@media (max-width: 920px) { .question-heading { align-items: start; flex-direction: column; }.project-picker { width: 100%; }.answer-layout { grid-template-columns: 1fr; }.retrieval-stats { grid-template-columns: repeat(2, 1fr); }.retrieval-stats div:nth-child(2) { border-right: 0; } }
@media (max-width: 760px) { .question-page { height: calc(100% - 72px); padding: 22px 16px 115px; }.question-heading h1 { font-size: 28px; }.ask-card, .answer-card, .evidence-panel { padding: 17px; }.ask-footer { align-items: start; flex-direction: column; }.ask-footer > div { width: 100%; }.ask-footer button { flex: 1; }.retrieval-stats { grid-template-columns: 1fr 1fr; } }
.ask-footer small, .retrieval-stats dt, .no-evidence { color: #435e64; }
</style>
