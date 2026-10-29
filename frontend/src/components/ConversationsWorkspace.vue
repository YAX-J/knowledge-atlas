<script setup lang="ts">
import { ref, watch } from 'vue'
import type { ApiProject, ApiProjectList } from '../api/knowledgeAtlas'
import type { EvidenceLocator, QuestionRetrievalMode } from '../types'
import QuestionWorkspace from './QuestionWorkspace.vue'
import { useConversations } from '../composables/useConversations'

const props = defineProps<{ project: ApiProject | null; projects: ApiProjectList | null; projectsLoading: boolean; projectsError: string; conversationId?: string }>()
const emit = defineEmits<{ selectProject: [project: ApiProject]; retryProjects: []; openEntity: [id: string]; openEvidence: [locator: EvidenceLocator]; conversation: [id:string] }>()
const { conversations, turns, selectedId, result, loading, sending, busy, error, unknown, retryTurn, refresh, select, start, send } = useConversations(() => props.project?.id)
const retryConfirmed = ref(false)
watch(()=>[props.project?.id,props.conversationId],()=>{
  if(props.project && props.conversationId && props.conversationId!==selectedId.value)void select(props.conversationId)
},{immediate:true})
watch(selectedId,value=>emit('conversation',value))
function retry() {
  const turn = retryTurn.value
  if (!turn || !retryConfirmed.value) return
  retryConfirmed.value = false
  void send(turn.question, turn.retrieval_mode, turn)
}
function ask(question: string, mode: QuestionRetrievalMode) { void send(question, mode) }
</script>

<template>
  <main class="conversation-workspace" aria-label="持久化证据会话">
    <aside class="conversation-history" aria-labelledby="conversation-history-title">
      <div class="conversation-heading"><h2 id="conversation-history-title">我的会话</h2><button type="button" :disabled="!project || sending || loading" @click="start">新建会话</button></div>
      <p>会话按项目保存。追问可参考最近六轮上下文，每次回答重新核对当前证据。</p>
      <button type="button" :disabled="!project || sending || loading" @click="refresh()">{{ loading ? '正在读取…' : '刷新会话与处理状态' }}</button>
      <p v-if="!loading && !conversations?.items.length">还没有会话。提出第一个问题后会自动保存。</p>
      <div class="conversation-list" tabindex="0" aria-label="已保存会话">
        <button v-for="item in conversations?.items ?? []" :key="item.id" type="button" :aria-pressed="item.id === selectedId" :disabled="sending" @click="select(item.id)"><strong>{{ item.title }}</strong><small>{{ new Date(item.updated_at).toLocaleString() }}</small></button>
      </div>
      <nav v-if="conversations && conversations.total > conversations.page_size" aria-label="会话分页"><button :disabled="loading || conversations.page <= 1" @click="refresh(conversations.page - 1)">上一页</button><span>{{ conversations.page }}</span><button :disabled="loading || conversations.page * conversations.page_size >= conversations.total" @click="refresh(conversations.page + 1)">下一页</button></nav>
      <section v-if="turns" aria-labelledby="turn-history-title"><h3 id="turn-history-title">本次会话</h3>
        <p class="history-notice">历史回答保存当时的证据快照；知识更新后，请重新提问确认当前结论。</p>
        <ol class="turn-list"><li v-for="turn in turns.items" :key="turn.id"><button type="button" :disabled="!turn.answer || sending" @click="result = turn.answer"><span>{{ turn.question }}</span><small>{{ { succeeded: '已回答', running: '处理中', failed: '失败', interrupted: '已中断' }[turn.status] }}</small></button></li></ol>
        <nav v-if="turns.total > turns.page_size" aria-label="问答轮次分页"><button :disabled="loading || turns.page <= 1" @click="refresh(conversations?.page, turns.page - 1)">上一页</button><span>{{ turns.page }}</span><button :disabled="loading || turns.page * turns.page_size >= turns.total" @click="refresh(conversations?.page, turns.page + 1)">下一页</button></nav>
      </section>
      <p v-if="unknown" role="alert">处理结果尚未确认。请先刷新状态，避免重复计费。</p>
      <form v-if="retryTurn && !unknown" @submit.prevent="retry"><p>上一轮失败或中断，重新请求可能再次计费。</p><label><input v-model="retryConfirmed" type="checkbox" />确认重新请求此轮回答</label><button :disabled="!retryConfirmed || busy" type="submit">重新请求</button></form>
    </aside>
    <QuestionWorkspace class="conversation-answer" :projects="projects" :project="project" :projects-loading="projectsLoading" :projects-error="projectsError" :result="result" :loading="sending || busy" :error="error" persistent
      @select-project="emit('selectProject', $event)" @retry-projects="emit('retryProjects')" @ask="ask" @retry="refresh()" @clear="result = null" @open-entity="emit('openEntity', $event)" @open-evidence="emit('openEvidence', $event)" />
  </main>
</template>

<style scoped>
.conversation-workspace { display: grid; grid-template-columns: 280px minmax(0,1fr); height: calc(100% - 104px); background: #edf3f3; }
.conversation-history { overflow: auto; padding: 24px 18px; border-right: 1px solid var(--line); background: #f8fbfb; }
.conversation-heading { display: flex; align-items: center; justify-content: space-between; gap: 10px; }h2 { margin: 0; font-size: 17px; }h3 { font-size: 14px; margin-top: 28px; }
p,small { color: #435e64; font-size: 12px; line-height: 1.8; }button { cursor: pointer; padding: 9px; min-height: 38px; border: 1px solid var(--line); border-radius: 4px; background: white; color: var(--ink); }button:disabled { opacity: .5; cursor: not-allowed; }
.conversation-list { max-height: 34vh; overflow: auto; margin-top: 20px; }.conversation-list button,.turn-list button { display: grid; gap: 5px; width: 100%; margin: 5px 0; text-align: left; overflow-wrap: anywhere; }.conversation-list button[aria-pressed=true] { border-color: var(--teal); background: var(--teal-soft); }
.turn-list { padding-left: 20px; max-height: 30vh; overflow: auto; }.history-notice { border-left: 2px solid var(--amber); padding-left: 10px; }.conversation-answer { height: 100% !important; padding: 26px !important; min-width: 0; }nav { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }form { display: grid; gap: 12px; margin-top: 22px; font-size: 12px; }
@media(max-width: 1000px) { .conversation-workspace { grid-template-columns: 220px minmax(0,1fr); } }
@media(max-width: 760px) { .conversation-workspace { grid-template-columns: 1fr; overflow: auto; height: calc(100% - 104px); }.conversation-history { max-height: 330px; }.conversation-answer { height: auto !important; } }
</style>
