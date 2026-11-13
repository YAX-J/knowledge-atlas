<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import { listRepositories, listSources, getCodeAnalysisContexts, type SourceListItem, type CodeAnalysisContexts, type SourceRepository } from '../../api/knowledgeAtlas'
import type { EvidenceLocator } from '../../types'
import { useProjectAssistant } from '../../composables/useProjectAssistant'
import AgentRunTrace from './AgentRunTrace.vue'
import { saveAssistantArtifact } from '../../api/assistant'

const props = defineProps<{projectId?: string; disabled?: boolean;noteRevisionIds?:string[]}>()
const emit = defineEmits<{openSource: [id: string]; openEvidence: [locator: EvidenceLocator]; sending: [value: boolean];openNote:[id:string];clearNotes:[];notesChanged:[]}>()
const {history, selected, loading, sending, unknown, error, busy, refresh, select, submit, retry, cancel, resume,approve,approvalUnknown,retryApproval} = useProjectAssistant(() => props.projectId)
const actions=ref<string[]>([]),repositoryId=ref(''),repositoryCommit=ref(''),artifactSaving=ref(false)
const wholeRepository = ref(false), repositoryRef = ref(''), repositories = ref<SourceRepository[]>([])
const repositoryPage = ref(1), repositoryTotal = ref(0), repositoryLoading = ref(false), repositoryError = ref('')
let repositoryReads = 0
const preparation = computed(() => selected.value?.scope.repository_progress)
const preparationLabel = { importing: '正在分批导入', parsing: '正在解析文件', reporting: '报告阶段' }
const actionLabels:Record<string,string>={create_note_draft:'创建新笔记草稿',propose_note_revision:'提出已有笔记修订（需审批）',request_source_parse:'创建笔记快照与解析资料',propose_knowledge:'抽取待审核知识候选',propose_knowledge_change:'提出正式知识变更（需审批）',import_repository_snapshot:'导入指定仓库提交',create_report_draft:'创建独立引用报告草稿'}
const unknownCount=computed(()=>(selected.value?.unknown_model_attempts??0)+(selected.value?.unknown_operations??0))
function start() {
  const base = { protocol: 'assistant-task-v3' as const, goal: goal.value.trim(), note_revision_ids: props.noteRevisionIds ?? [] }
  if (wholeRepository.value) {
    if (!repositoryId.value) return
    const ref = repositoryRef.value.trim()
    void submit({ ...base, source_ids: [], allowed_actions: ['import_repository_snapshot'], whole_repository: true,
      repository_id: repositoryId.value, ...(ref ? { repository_ref: ref } : {}) })
    return
  }
  void submit({ ...base, source_ids: chosen.value.map(s => s.id), allowed_actions: actions.value,
    ...(snapshot.value ? { snapshot_id: snapshot.value } : {}),
    ...(actions.value.includes('import_repository_snapshot') ? { repository_id: repositoryId.value, repository_commit: repositoryCommit.value } : {}) })
}
async function applyProposal(operation:import('../../api/assistant').AssistantOperation){await approve(operation,'approve');emit('notesChanged')}
async function saveArtifact(artifactId?:string){const project=props.projectId,task=selected.value,artifact=artifactId??task?.final_artifact_id??task?.artifact_ids?.at(-1);if(!project||!task||!artifact||artifactSaving.value)return
  artifactSaving.value=true
  try{const key=`ka-artifact-note:${project}:${artifact}`,id=sessionStorage.getItem(key)??crypto.randomUUID();sessionStorage.setItem(key,id);const note=await saveAssistantArtifact(project,task.id,artifact,id);if(project===props.projectId){emit('notesChanged');emit('openNote',note.current.id)}}
  catch(cause){if(project===props.projectId)error.value=cause instanceof Error?cause.message:'保存草稿结果未知；重试将沿用同一标识。'}finally{if(project===props.projectId)artifactSaving.value=false}}
const acknowledgeUnknown=ref(false)
watch(()=>[selected.value?.id,selected.value?.revision],()=>{acknowledgeUnknown.value=false})
const goal = ref(''), sources = ref<SourceListItem[]>([]), chosen = ref<SourceListItem[]>([]), sourcePage = ref(1), sourceTotal = ref(0)
const sourceLoading = ref(false), sourceError = ref(''), contexts = ref<CodeAnalysisContexts | null>(null), snapshot = ref('')
const contextError = ref(''), contextLoading = ref(false)
let reads = 0, contextReads = 0, disposed = false
const locked = computed(() => busy.value || props.disabled)
const code = computed(() => chosen.value.find(item => item.source_type !== 'markdown'))
const labels = {queued:'等待 runner',running: '正在执行',waiting_approval:'等待人工审批', succeeded: '已结束', failed: '未完成', interrupted: '执行已中断',cancelled:'已取消'}
const referenceLabels = {source: '原始资料', code: '源码 / 派生结构', knowledge: '已确认知识',note:'笔记固定修订'}
function openReference(id: string) {
  const reference = selected.value?.result?.references.find(item => item.id === id)
  if (!reference) return
  if(reference.kind==='note'&&reference.revision_id)emit('openNote',reference.revision_id)
  else if (reference.chunk_id&&reference.source_id) emit('openEvidence', {source_id: reference.source_id, chunk_id: reference.chunk_id})
  else if(reference.source_id) emit('openSource', reference.source_id)
}
watch(sending, value => emit('sending', value))
async function loadRepositories(page = 1) {
  const project = props.projectId, request = ++repositoryReads
  if (!project) return
  repositoryLoading.value = true; repositoryError.value = ''
  try {
    const result = await listRepositories(project, page, 20)
    if (disposed || request !== repositoryReads || project !== props.projectId) return
    repositories.value = result.items.filter(item => item.provider === 'github')
    repositoryPage.value = result.page
    repositoryTotal.value = result.total
    if (!repositories.value.some(item => item.id === repositoryId.value)) repositoryId.value = repositories.value[0]?.id ?? ''
  } catch (cause) {
    if (!disposed && request === repositoryReads) repositoryError.value = cause instanceof Error ? cause.message : '仓库列表读取失败。'
  } finally {
    if (!disposed && request === repositoryReads) repositoryLoading.value = false
  }
}
watch(wholeRepository, enabled => {
  repositoryId.value = ''
  if (enabled) void loadRepositories()
  else { repositoryReads++; repositoryLoading.value = false }
})
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
  actions.value=[];repositoryId.value='';repositoryCommit.value='';artifactSaving.value=false
  repositoryReads++; wholeRepository.value = false; repositoryRef.value = ''; repositories.value = []
  repositoryPage.value = 1; repositoryTotal.value = 0; repositoryLoading.value = false; repositoryError.value = ''
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
onScopeDispose(() => {disposed = true; reads++; contextReads++; repositoryReads++})
</script>

<template>
  <section class="project-assistant" aria-labelledby="project-assistant-title">
    <header><div><span class="assistant-kicker">PROJECT ASSISTANT · M3 / M4</span><h2 id="project-assistant-title">项目助手</h2>
      <p>结合固定资料、笔记与已确认知识整理报告。默认只读；已有内容与正式知识变更必须审批。共享最多 8 次模型请求、16 次工具执行。</p></div>
      <button type="button" :disabled="!projectId || loading || sending" @click="refresh()">刷新助手任务</button></header>
    <div class="assistant-layout">
      <div class="assistant-input">
        <form aria-label="项目助手目标" @submit.prevent="start">
          <fieldset :disabled="!projectId || locked"><label for="assistant-goal">希望了解或整理什么</label>
            <textarea id="assistant-goal" v-model="goal" rows="4" maxlength="2000" required placeholder="结合文档、已确认知识和所选源码，解释主要模块，并列出有记录依据的未决问题。" />
            <label class="assistant-source"><input v-model="wholeRepository" type="checkbox" />同步并解析整个 GitHub 仓库</label>
            <template v-if="wholeRepository">
              <label>GitHub 仓库<select v-model="repositoryId" required :disabled="repositoryLoading">
                <option value="" disabled>选择已登记的仓库</option>
                <option v-for="repository in repositories" :key="repository.id" :value="repository.id">{{ repository.name }}</option>
              </select></label>
              <nav v-if="repositoryTotal > 20" aria-label="助手仓库分页">
                <button type="button" :disabled="repositoryLoading || repositoryPage <= 1" @click="loadRepositories(repositoryPage - 1)">上一页</button>
                <span>{{ repositoryPage }}</span>
                <button type="button" :disabled="repositoryLoading || repositoryPage * 20 >= repositoryTotal" @click="loadRepositories(repositoryPage + 1)">下一页</button>
              </nav>
              <p v-if="repositoryError" role="alert">{{ repositoryError }} <button type="button" @click="loadRepositories(repositoryPage)">重试</button></p>
              <p v-else-if="!repositories.length && !repositoryLoading">本页没有 GitHub 仓库。可在资料页登记仓库。</p>
              <label>分支、标签或提交<input v-model="repositoryRef" maxlength="255" placeholder="留空使用默认分支" /></label>
              <p>后台固定提交、导入并解析受支持文件，再选取最多 20 份资料生成带原文引用的报告。</p>
            </template>
            <template v-else>
            <p>本次范围：当前项目已确认知识 + 所选 {{chosen.length}} 份不可变资料版本（最多 20 份 / 200 KB）。未选择资料时仅检索已确认知识。</p>
            <div class="assistant-sources" aria-label="助手资料范围" :aria-busy="sourceLoading">
              <p v-if="sourceLoading">正在读取资料…</p><p v-else-if="!sources.length">暂无资料，请先在资料工作台上传并解析。</p>
              <label v-for="item in sources" :key="item.id" class="assistant-source"><input type="checkbox"
                :checked="chosen.some(source => source.id === item.id)" :disabled="item.status !== 'ready' && !actions.includes('request_source_parse') || chosen.length >= 20 && !chosen.some(source => source.id === item.id)"
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
            <p>已附加 {{noteRevisionIds?.length??0}} 个固定笔记修订。<button v-if="noteRevisionIds?.length" type="button" @click="emit('clearNotes')">清空笔记附件</button></p>
            <details><summary>本次允许的操作</summary><p>选中即授权创建相应草稿或待审核候选。已有内容和正式知识的提案仍需逐项审批；未选操作会被后端拒绝。</p>
              <label v-for="(label,action) in actionLabels" :key="action" class="assistant-source"><input v-model="actions" type="checkbox" :value="action" />{{label}}</label>
              <template v-if="actions.includes('import_repository_snapshot')"><label>仓库 UUID<input v-model="repositoryId" required pattern="[0-9a-fA-F-]{36}" /></label><label>固定提交 SHA<input v-model="repositoryCommit" required pattern="[0-9a-f]{40}" maxlength="40" /></label></template>
            </details>
            </template>
            <button type="submit" :disabled="!goal.trim() || wholeRepository && (!repositoryId || repositoryLoading)">{{sending ? '正在保存目标…' : wholeRepository ? '开始整仓任务' : actions.length?'开始已授权任务':'开始只读任务'}}</button>
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
          <p>已保存范围：{{selected.scope.source_ids.length}} 份资料 · {{selected.scope.note_versions?.length??0}} 个笔记修订 · {{selected.scope.commit_sha ? `提交 ${selected.scope.commit_sha}` : '精确来源 UUID'}} · {{selected.scope.valid_at || '当前已确认知识'}}</p>
          <p v-if="preparation" role="status">
            {{ preparationLabel[preparation.phase] }} · 已导入处理 {{ preparation.completed_files }} / {{ preparation.total_files }} 个文件
            <span v-if="preparation.pending_directories"> · 待遍历 {{ preparation.pending_directories }} 个目录</span>
            <span v-if="preparation.parsed_files !== undefined"> · 已解析 {{ preparation.parsed_files }} · 失败 {{ preparation.failed_files }} · 跳过 {{ preparation.skipped_files }}</span>
            <span v-if="preparation.commit_sha"> · {{ preparation.ref }} @ {{ preparation.commit_sha.slice(0, 12) }}</span>
          </p>
          <details v-if="selected.scope.note_versions?.length||selected.scope.allowed_actions?.length"><summary>保存的笔记版本与操作授权</summary><p v-for="revision in selected.scope.note_versions??[]" :key="revision.id">修订 {{revision.id}} · {{revision.sha256.slice(0,12)}}</p><p>允许：{{selected.scope.allowed_actions?.map(a=>actionLabels[a]??a).join('、')||'只读'}}</p></details>
          <p v-if="selected.execution_mode!=='sync_v1'">剩余协调请求 {{selected.remaining?.model??Math.max(0,4-(selected.usage.model??0))}} 次 · 工具 {{selected.remaining?.tool??Math.max(0,8-(selected.usage.tool??0))}} 次</p>
          <p v-if="selected.error_code" role="alert">任务未完成（{{selected.error_code}}）。{{selected.can_continue?'请核对记录后选择继续或新建目标。':'请核对记录后显式新建目标。'}}</p>
          <p v-if="selected.status==='queued'" role="status">任务已保存，等待独立 runner 认领。刷新页面只读取状态。</p>
          <button v-if="selected.execution_mode!=='sync_v1' && ['queued','running','failed','interrupted','waiting_approval'].includes(selected.status)" type="button" :disabled="sending" @click="cancel">取消后续步骤</button>
          <section v-if="selected.operations?.length" aria-label="操作提案与回执"><h4>操作提案与回执</h4><p v-if="approvalUnknown" role="alert">审批结果尚未确认，请先刷新读取。<button type="button" :disabled="sending" @click="retryApproval">显式重发同一审批</button></p>
            <article v-for="operation in selected.operations" :key="operation.id"><strong>{{actionLabels[operation.kind]??operation.kind}} · {{operation.status}}</strong><p>提案校验 {{operation.proposal_sha256.slice(0,12)}} <span v-if="operation.error_code">· {{operation.error_code}}</span></p>
              <details :open="operation.status==='pending'"><summary>查看精确输入、修改前版本和结果</summary><pre>{{JSON.stringify(operation.payload,null,2)}}</pre><pre v-if="operation.result">{{JSON.stringify(operation.result,null,2)}}</pre></details>
              <button v-if="operation.kind==='create_report_draft'&&typeof operation.result?.artifact_id==='string'" type="button" :disabled="artifactSaving" @click="saveArtifact(operation.result.artifact_id)">保存此报告草稿为笔记</button>
              <template v-if="operation.status==='pending'&&selected.status==='waiting_approval'"><p>请核对完整内容和对象版本。拒绝提案不会修改已有候选的审核状态。</p><button type="button" :disabled="sending||approvalUnknown" @click="applyProposal(operation)">确认应用此提案</button><button type="button" :disabled="sending||approvalUnknown" @click="approve(operation,'reject')">拒绝此提案</button></template>
            </article></section>
          <div v-if="selected.can_continue" class="assistant-question"><p>继续将复用已保存检查点，并沿用剩余预算。</p>
            <label v-if="unknownCount" class="assistant-source"><input v-model="acknowledgeUnknown" type="checkbox" /><span>已知 {{unknownCount}} 次调用或操作结果未知，仍计入用量；继续可能发起新的付费尝试。</span></label>
            <button type="button" :disabled="sending || !!unknownCount && !acknowledgeUnknown" @click="resume(acknowledgeUnknown)">按保存检查点继续</button></div>
          <div v-if="selected.result?.action === 'ask_user'" class="assistant-question"><h4>需要补充信息</h4><p>{{selected.result.question}}</p><p>请在目标中补充信息后提交新任务。</p></div>
          <section v-if="selected.result?.report" aria-label="项目引用报告"><h4>{{selected.result.report.title}}</h4>
            <button v-if="selected.artifact_ids?.length" type="button" :disabled="artifactSaving" @click="saveArtifact()">保存报告为可编辑笔记草稿</button>
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
