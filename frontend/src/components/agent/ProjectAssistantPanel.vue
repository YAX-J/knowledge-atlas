<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { listSources, getCodeAnalysisContexts, type SourceListItem, type CodeAnalysisContexts } from '../../api/knowledgeAtlas'
import type { EvidenceLocator } from '../../types'
import { useProjectAssistant } from '../../composables/useProjectAssistant'
import AgentRunTrace from './AgentRunTrace.vue'

const props = defineProps<{projectId?: string; disabled?: boolean}>()
const emit = defineEmits<{openSource: [id: string]; openEvidence: [locator: EvidenceLocator]; sending: [value: boolean]}>()
const {history, selected, loading, sending, unknown, error, busy, refresh, select, submit, retry, cancel, resume} = useProjectAssistant(() => props.projectId)
const acknowledgeUnknown=ref(false)
watch(()=>[selected.value?.id,selected.value?.revision],()=>{acknowledgeUnknown.value=false})
const goal = ref(''), sources = ref<SourceListItem[]>([]), chosen = ref<SourceListItem[]>([]), sourcePage = ref(1), sourceTotal = ref(0)
const sourceLoading = ref(false), sourceError = ref(''), contexts = ref<CodeAnalysisContexts | null>(null), snapshot = ref('')
const contextError = ref(''), contextLoading = ref(false)
let reads = 0, contextReads = 0, disposed = false
const locked = computed(() => busy.value || props.disabled)
const code = computed(() => chosen.value.find(item => item.source_type !== 'markdown'))
const labels = {queued:'等待 runner',running: '正在执行', succeeded: '已结束', failed: '未完成', interrupted: '执行已中断',cancelled:'已取消'}
const referenceLabels = {source: '原始资料', code: '源码 / 派生结构', knowledge: '已确认知识'}
function openReference(id: string) {
  const reference = selected.value?.result?.references.find(item => item.id === id)
  if (!reference) return
  if (reference.chunk_id) emit('openEvidence', {source_id: reference.source_id, chunk_id: reference.chunk_id})
  else emit('openSource', reference.source_id)
}
watch(sending, value => emit('sending', value))
async function loadSources(page = 1) {
  const id = props.projectId, read = ++reads
  if (!id) return
  sourceLoading.value = true; sourceError.value = ''
  try {
    const result = await listSources(id, page, 20)
    if (disposed || read !== reads || props.projectId !== id) return
    sources.value = result.items; sourcePage.value = page; sourceTotal.value = result.total
  } catch (cause) { if (!disposed && read === reads) sourceError.value = cause instanceof Error ? cause.message : '资料读取失败' }
  finally { if (!disposed && read === reads) sourceLoading.value = false }
}
function toggle(source: SourceListItem, checked: boolean) {
  if (checked && chosen.value.length < 20) chosen.value = [...chosen.value, source]
  else if (!checked) chosen.value = chosen.value.filter(item => item.id !== source.id)
}
watch(() => props.projectId, () => {
  reads++; contextReads++; goal.value = ''; sources.value = []; chosen.value = []; snapshot.value = ''; contexts.value = null
  contextError.value = ''; contextLoading.value = false
  sourcePage.value = 1; sourceTotal.value = 0; sourceLoading.value = false; sourceError.value = ''
  void loadSources()
}, {immediate: true, flush: 'sync'})
async function loadContexts() {
  const id = code.value?.id
  const read = ++contextReads, project = props.projectId
  contexts.value = null; snapshot.value = ''; contextError.value = ''; contextLoading.value = false
  if (!id) return
  contextLoading.value = true
  try {
    const result = await getCodeAnalysisContexts(id)
    if (!disposed && read === contextReads && project === props.projectId) contexts.value = result
  } catch (cause) {
    if (!disposed && read === contextReads && project === props.projectId) contextError.value = cause instanceof Error ? cause.message : '代码快照读取失败'
  } finally { if (!disposed && read === contextReads) contextLoading.value = false }
}
watch(() => code.value?.id, () => {void loadContexts()})
onScopeDispose(() => {disposed = true; reads++; contextReads++})
</script>

<template>
  <section class="project-assistant" aria-labelledby="project-assistant-title">
    <header><div><span class="assistant-kicker">PROJECT ASSISTANT · M2</span><h2 id="project-assistant-title">项目只读助手</h2>
      <p>描述目标，结合选定资料、源码与已确认知识形成引用报告。最多 4 次协调请求、8 次工具执行。</p></div>
      <button type="button" :disabled="!projectId || loading || sending" @click="refresh()">刷新助手任务</button></header>
    <div class="assistant-layout">
      <div class="assistant-input">
        <form aria-label="项目助手目标" @submit.prevent="submit({goal: goal.trim(), source_ids: chosen.map(item => item.id), ...(snapshot ? {snapshot_id: snapshot} : {})})">
          <fieldset :disabled="!projectId || locked"><label for="assistant-goal">希望了解或整理什么</label>
            <textarea id="assistant-goal" v-model="goal" rows="4" maxlength="2000" required placeholder="结合文档、已确认知识和所选源码，解释主要模块，并列出有记录依据的未决问题。" />
            <p>本次范围：当前项目已确认知识 + 所选 {{chosen.length}} 份不可变资料版本（最多 20 份 / 200 KB）。未选择资料时仅检索已确认知识。</p>
            <div class="assistant-sources" aria-label="助手资料范围" :aria-busy="sourceLoading">
              <p v-if="sourceLoading">正在读取资料…</p><p v-else-if="!sources.length">暂无资料，请先在资料工作台上传并解析。</p>
              <label v-for="item in sources" :key="item.id" class="assistant-source"><input type="checkbox"
                :checked="chosen.some(source => source.id === item.id)" :disabled="item.status !== 'ready' || chosen.length >= 20 && !chosen.some(source => source.id === item.id)"
                @change="toggle(item, ($event.target as HTMLInputElement).checked)" />
                <span>{{item.relative_path || item.original_name}} <small>{{item.source_type}} · 版本 {{item.id.slice(0, 8)}} · {{item.status === 'ready' ? '已解析' : '待解析'}}</small></span></label>
            </div>
            <p v-if="chosen.length">已选版本：{{chosen.map(item => `${item.relative_path || item.original_name} (${item.id.slice(0, 8)})`).join('、')}}</p>
            <nav v-if="sourceTotal > 20" aria-label="助手资料分页"><button type="button" :disabled="sourceLoading || sourcePage <= 1" @click="loadSources(sourcePage - 1)">上一页</button>
              <span>{{sourcePage}}</span><button type="button" :disabled="sourceLoading || sourcePage * 20 >= sourceTotal" @click="loadSources(sourcePage + 1)">下一页</button></nav>
            <label v-if="code">代码版本范围<select v-model="snapshot" aria-label="助手代码快照"><option value="">精确使用已选来源版本</option>
              <option v-for="item in contexts?.snapshots ?? []" :key="item.id" :value="item.id">{{item.ref}} · {{item.commit_sha.slice(0, 12)}}{{item.truncated ? '（部分快照）' : ''}}</option></select></label>
            <p v-if="snapshot">所选代码必须全部属于这个提交；后端会拒绝混合版本。</p>
            <p v-if="contextLoading">正在读取代码快照…</p>
            <p v-if="contextError" role="alert">{{contextError}}。仍可使用已选精确来源版本。<button type="button" @click="loadContexts">重新读取快照</button></p>
            <button type="submit" :disabled="!goal.trim()">{{sending ? '正在处理目标…' : '开始只读任务'}}</button>
          </fieldset>
        </form>
        <p v-if="sourceError" role="alert">{{sourceError}} <button type="button" :disabled="sourceLoading || !projectId" @click="loadSources(sourcePage)">重新读取资料</button></p>
        <p v-if="unknown" role="alert">提交结果尚未确认。请先刷新读取；显式重发会保留同一任务 UUID。</p>
        <button v-if="unknown" type="button" :disabled="sending || loading" @click="retry">重发同一助手任务</button>
        <p v-if="error" role="alert">{{error}}</p>
      </div>
      <div class="assistant-output" aria-label="助手任务与报告">
        <p v-if="!history?.items.length && !loading">还没有项目助手任务。</p>
        <div class="assistant-history"><button v-for="item in history?.items ?? []" :key="item.id" type="button" :disabled="sending || unknown"
          :aria-pressed="selected?.id === item.id" @click="select(item.id)">{{item.goal}} · {{labels[item.status]}}</button></div>
        <nav v-if="history && history.total > history.page_size" aria-label="助手任务分页"><button type="button" :disabled="loading || history.page <= 1" @click="refresh(history.page - 1)">上一页</button>
          <span>{{history.page}}</span><button type="button" :disabled="loading || history.page * history.page_size >= history.total" @click="refresh(history.page + 1)">下一页</button></nav>
        <p v-if="loading" role="status">正在读取任务…</p>
        <article v-if="selected" :aria-busy="selected.status === 'running'"><h3>{{selected.goal}}</h3><p>{{labels[selected.status]}} · 模型 {{selected.usage.model ?? 0}} / {{selected.usage.limits?.model ?? 8}} · 工具 {{selected.usage.tool ?? 0}} / {{selected.usage.limits?.tool ?? 16}} · 嵌入 {{selected.usage.embedding ?? 0}}</p>
          <p>已保存范围：{{selected.scope.source_ids.length}} 份资料 · {{selected.scope.commit_sha ? `提交 ${selected.scope.commit_sha}` : '精确来源 UUID'}} · {{selected.scope.valid_at || '当前已确认知识'}}</p>
          <p v-if="selected.execution_mode==='async_v2'">剩余协调请求 {{Math.max(0,Math.min(4,selected.usage.limits?.model ?? 8)-(selected.usage.model ?? 0))}} 次 · 工具 {{Math.max(0,Math.min(8,selected.usage.limits?.tool ?? 16)-(selected.usage.tool ?? 0))}} 次</p>
          <p v-if="selected.error_code" role="alert">任务未完成（{{selected.error_code}}）。{{selected.can_continue?'请核对记录后选择继续或新建目标。':'请核对记录后显式新建目标。'}}</p>
          <p v-if="selected.status==='queued'" role="status">任务已保存，等待独立 runner 认领。刷新页面只读取状态。</p>
          <button v-if="selected.execution_mode==='async_v2' && ['queued','running','failed','interrupted'].includes(selected.status)" type="button" :disabled="sending" @click="cancel">取消后续步骤</button>
          <div v-if="selected.can_continue" class="assistant-question"><p>继续将复用已保存检查点，并沿用剩余预算。</p>
            <label v-if="selected.unknown_model_attempts" class="assistant-source"><input v-model="acknowledgeUnknown" type="checkbox" /><span>已知 {{selected.unknown_model_attempts}} 次调用结果未知，仍计入用量；继续可能发起新的付费尝试。</span></label>
            <button type="button" :disabled="sending || !!selected.unknown_model_attempts && !acknowledgeUnknown" @click="resume(acknowledgeUnknown)">按保存检查点继续</button></div>
          <div v-if="selected.result?.action === 'ask_user'" class="assistant-question"><h4>需要补充信息</h4><p>{{selected.result.question}}</p><p>请在目标中补充信息后提交新任务。</p></div>
          <section v-if="selected.result?.report" aria-label="项目引用报告"><h4>{{selected.result.report.title}}</h4>
            <article v-for="(claim, index) in selected.result.report.claims" :key="index"><p><strong>{{claim.status === 'referenced' ? '附有引用' : '待验证'}}：</strong>{{claim.text}}</p>
              <button v-for="id in claim.reference_ids" :key="id" type="button" @click="openReference(id)">查看引用 {{selected.result.references.findIndex(ref => ref.id === id) + 1}}</button></article>
            <p v-for="missing in selected.result.report.missing_information" :key="missing">缺少信息：{{missing}}</p>
            <details v-for="(reference, index) in selected.result.references" :key="reference.id"><summary>[{{index + 1}}] {{referenceLabels[reference.kind]}} · {{reference.path}}:{{reference.start_line}}–{{reference.end_line}}</summary>
              <p>版本 {{reference.source_sha256.slice(0, 12)}}<span v-if="reference.commit_sha"> · 提交 {{reference.commit_sha}}</span></p><pre>{{reference.quote}}</pre></details>
          </section>
          <AgentRunTrace :events="selected.events" />
        </article>
      </div>
    </div>
  </section>
</template>

<style scoped>
.project-assistant{margin:24px 0;padding:22px;border:1px solid var(--line,#c9d5d7);border-top:3px solid var(--teal,#215b60);background:var(--paper,#f8fbfb);min-width:0}.project-assistant header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}.assistant-kicker{font-size:11px;letter-spacing:.1em;color:var(--teal)}h2{font-size:20px;margin:8px 0}.assistant-layout{display:grid;grid-template-columns:minmax(260px,360px) minmax(0,1fr);gap:24px}.assistant-input,.assistant-output{min-width:0}p,small{font-size:12px;line-height:1.8;overflow-wrap:anywhere}label{display:grid;gap:7px;font-size:13px}fieldset{border:0;padding:0;min-width:0}textarea,select{box-sizing:border-box;width:100%;padding:10px;font:inherit;color:var(--ink);border:1px solid #a8bdbf;background:#fff;resize:vertical}button{padding:8px 12px;min-height:36px;border:1px solid #a8bdbf;background:#fff;color:var(--ink);font:inherit;font-size:12px;cursor:pointer;margin:5px 8px 5px 0;overflow-wrap:anywhere;max-width:100%;text-align:left}button:disabled,fieldset:disabled{opacity:.6}button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible,summary:focus-visible{outline:2px solid var(--rose,#a75870);outline-offset:3px}.assistant-sources{max-height:220px;overflow:auto;border-block:1px solid var(--line,#c9d5d7);padding:8px 0}.assistant-source{display:flex;align-items:start;gap:8px;margin:7px 0;overflow-wrap:anywhere}.assistant-source span{min-width:0}.assistant-source small{display:block}.assistant-history{max-height:150px;overflow:auto}.assistant-history [aria-pressed=true]{background:#f7eaf0;border-color:var(--rose)}.assistant-output{max-height:780px;overflow:auto;padding-inline:4px}.assistant-question{padding:12px;background:#fff9e9;border-left:2px solid #d8a62c}details{font-size:12px;border-top:1px solid var(--line);padding:10px 0}summary{cursor:pointer;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;line-height:1.7;background:#edf3f3;padding:10px}nav{display:flex;align-items:center;gap:6px}@media(max-width:1000px){.assistant-layout{grid-template-columns:1fr}}
</style>
