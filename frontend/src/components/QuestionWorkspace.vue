<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ApiProject, ApiProjectList } from '../api/knowledgeAtlas'
import type { QuestionAnswer } from '../types'

const props = defineProps<{
  projects: ApiProjectList | null
  project: ApiProject | null
  projectsLoading: boolean
  projectsError: string
  result: QuestionAnswer | null
  loading: boolean
  error: string
}>()
const emit = defineEmits<{
  selectProject: [project: ApiProject]
  retryProjects: []
  ask: [question: string]
  retry: []
  clear: []
  openEntity: [id: string]
}>()
const question = ref('')
const remaining = computed(() => 200 - question.value.length)
const coverage = computed(() => {
  const result = props.result
  if (!result?.retrieval.eligible_count) return '0%'
  return `${Math.round(result.retrieval.indexed_count / result.retrieval.eligible_count * 100)}%`
})

watch(() => props.project?.id, () => { question.value = '' })

function selectProject(event: Event) {
  const id = (event.target as HTMLSelectElement).value
  const selected = props.projects?.items.find(item => item.id === id)
  if (selected) emit('selectProject', selected)
}
function submit() {
  const value = question.value.trim()
  if (value && value.length <= 200 && props.project && !props.loading) emit('ask', value)
}
</script>

<template>
  <main class="question-page" aria-labelledby="question-title">
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

    <section class="ask-card" aria-label="提问">
      <form @submit.prevent="submit">
        <label for="evidence-question">你想从项目知识中确认什么？</label>
        <textarea id="evidence-question" v-model="question" maxlength="200" rows="4"
          :disabled="loading || !project" placeholder="例如：项目为什么选择 PostgreSQL，而没有采用其他方案？" />
        <div class="ask-footer">
          <small>{{ remaining }} 字可用 · 当前回答不会保存为历史记录</small>
          <div>
            <button v-if="result || error" type="button" :disabled="loading" @click="emit('clear')">清除回答</button>
            <button class="primary" type="submit" :disabled="loading || !project || !question.trim()">
              {{ loading ? '正在检索证据…' : '检索并回答' }}
            </button>
          </div>
        </div>
      </form>
    </section>

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
      <span class="pulse" aria-hidden="true">◎</span><h2>正在组合关键词、语义与图关系</h2><p>随后会让模型只依据检索到的原文证据作答。</p>
    </section>
    <section v-else-if="error" class="question-state error-state" role="alert">
      <span aria-hidden="true">!</span><h2>这次没有得到可确认的结果</h2><p>{{ error }}</p><button type="button" @click="emit('retry')">重试本次问题</button>
    </section>
    <section v-else-if="result" class="answer-layout">
      <article class="answer-card">
        <div class="answer-status" :class="{ unsupported: !result.supported }">
          <span>{{ result.supported ? '证据支持' : '证据不足' }}</span>
          <strong>{{ Math.round(result.confidence * 100) }}% 置信度</strong>
        </div>
        <p class="asked">{{ result.question }}</p>
        <h2>{{ result.supported ? '回答' : '暂不能确认' }}</h2>
        <p class="answer-text">{{ result.answer }}</p>
        <template v-if="result.missing_information.length">
          <h3>仍需补充</h3>
          <ul><li v-for="item in result.missing_information" :key="item">{{ item }}</li></ul>
        </template>
        <dl class="retrieval-stats">
          <div><dt>关键词命中</dt><dd>{{ result.retrieval.keyword_hits }}</dd></div>
          <div><dt>语义命中</dt><dd>{{ result.retrieval.vector_hits }}</dd></div>
          <div><dt>图关系命中</dt><dd>{{ result.retrieval.graph_hits }}</dd></div>
          <div><dt>语义索引覆盖</dt><dd>{{ coverage }}</dd></div>
        </dl>
      </article>

      <aside class="evidence-panel" aria-label="回答引用的原文证据">
        <div class="evidence-heading"><span>引用证据</span><strong>{{ result.evidence.length }}</strong></div>
        <p v-if="!result.evidence.length" class="no-evidence">本次没有可引用的证据。</p>
        <article v-for="(item, index) in result.evidence" :key="item.id" class="evidence-card">
          <div><span>[{{ index + 1 }}]</span><button type="button" @click="emit('openEntity', item.entity_id)">{{ item.entity_name }} ↗</button></div>
          <strong>{{ item.title }}</strong>
          <small>第 {{ item.start_line }}–{{ item.end_line }} 行 · {{ item.heading_path.join(' / ') || '文档开头' }}</small>
          <blockquote>{{ item.quote }}</blockquote>
        </article>
      </aside>
    </section>
    <section v-else class="question-state">
      <span aria-hidden="true">?</span><h2>答案应当可以追溯</h2><p>每条支持性回答都会列出模型实际引用的原文片段，并可跳回对应图谱实体。</p>
    </section>
  </main>
</template>

<style scoped>
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
.evidence-card { margin-top: 16px; padding: 14px; border: 1px solid var(--line); border-radius: 5px; background: #fff; overflow-wrap: anywhere; }.evidence-card > div { display: flex; align-items: center; gap: 8px; margin-bottom: 9px; color: var(--teal); font-size: 11px; }.evidence-card button { min-height: 30px; padding: 4px 8px; border: 0; color: var(--teal); background: transparent; text-decoration: underline; }.evidence-card strong, .evidence-card small { display: block; }.evidence-card small { margin-top: 6px; color: #63797d; font-size: 10px; line-height: 1.6; }.evidence-card blockquote { margin: 12px 0 0; padding-left: 10px; border-left: 2px solid #a3b9b7; white-space: pre-wrap; font-size: 12px; line-height: 1.85; }
@media (max-width: 920px) { .question-heading { align-items: start; flex-direction: column; }.project-picker { width: 100%; }.answer-layout { grid-template-columns: 1fr; }.retrieval-stats { grid-template-columns: repeat(2, 1fr); }.retrieval-stats div:nth-child(2) { border-right: 0; } }
@media (max-width: 760px) { .question-page { height: calc(100% - 72px); padding: 22px 16px 115px; }.question-heading h1 { font-size: 28px; }.ask-card, .answer-card, .evidence-panel { padding: 17px; }.ask-footer { align-items: start; flex-direction: column; }.ask-footer > div { width: 100%; }.ask-footer button { flex: 1; }.retrieval-stats { grid-template-columns: 1fr 1fr; } }
</style>
