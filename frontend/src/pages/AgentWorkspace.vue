<script setup lang="ts">
import AnswerClaims from '../components/AnswerClaims.vue'
import { onScopeDispose, ref, watch } from 'vue'
import type { ApiProject, ApiProjectList, ApiSource } from '../api/knowledgeAtlas'
import { useAgentRuns } from '../composables/useAgentRuns'
import type { AgentRun } from '../api/agents'
import type { EvidenceLocator, QuestionRetrievalMode } from '../types'
import AgentRunTrace from '../components/agent/AgentRunTrace.vue'
import AgentCodeResult from '../components/agent/AgentCodeResult.vue'
import AgentWorkflowForm from '../components/agent/AgentWorkflowForm.vue'
import ProjectAssistantPanel from '../components/agent/ProjectAssistantPanel.vue'
import NotesPanel from '../components/agent/NotesPanel.vue'

const props=defineProps<{project:ApiProject|null;projects:ApiProjectList|null;source:ApiSource|null;runId?:string}>()
const emit=defineEmits<{selectProject:[project:ApiProject];openSource:[sourceId:string];openEvidence:[locator:EvidenceLocator];run:[id:string]}>()
const {runs,selected,loading,sending,unknown,error,busy,refresh,select,submit,resume,retry}=useAgentRuns(()=>props.project?.id)
const timeZone=Intl.DateTimeFormat().resolvedOptions().timeZone
const assistantSending=ref(false)
const noteAttachments=ref<string[]>([]),noteRevision=ref(''),noteRefresh=ref(0)
const noteOpenToken=ref(0)
function openNote(id:string){noteRevision.value=id;noteOpenToken.value++}
watch(()=>props.project?.id,()=>{noteAttachments.value=[];noteRevision.value='';noteRefresh.value++})
function attachNote(id:string){if(!noteAttachments.value.includes(id)&&noteAttachments.value.length<20)noteAttachments.value.push(id)}
const retrievalLabels:Record<QuestionRetrievalMode,string>={bm25:'BM25 词法',bm25_source:'BM25 + 来源位置',rrf:'BM25 + 向量融合',hybrid:'混合 + 图关系',vector:'语义向量'}
const status:Record<AgentRun['status'],string>={running:'正在协作',awaiting_review:'等待人工审核',succeeded:'已完成',failed:'未完成',interrupted:'执行已中断'}
watch(()=>[props.project?.id,props.runId],()=>{if(props.runId&&props.runId!==selected.value?.id)void select(props.runId)},{immediate:true})
watch(selected,value=>{if(value)emit('run',value.id)})
function changeProject(event:Event) {const value=props.projects?.items.find(item=>item.id===(event.target as HTMLSelectElement).value);if(value)emit('selectProject',value)}
const timer=setInterval(()=>{if(selected.value?.status==='running'&&!loading.value&&!sending.value)void refresh()},3000)
onScopeDispose(()=>clearInterval(timer))
</script>

<template>
  <main class="agent-workspace" aria-labelledby="agent-workspace-title">
    <header><div><span class="agent-kicker">Agent / 有证据的协作</span><h1 id="agent-workspace-title">协作任务</h1><p>代码分析、知识候选整理与证据问答共享任务范围。正式知识经过人工审核后入图。</p></div>
      <label>当前项目<select :value="project?.id??''" :disabled="sending||assistantSending" @change="changeProject"><option disabled value="">请选择项目</option><option v-for="item in projects?.items??[]" :key="item.id" :value="item.id">{{item.name}}</option></select></label></header>
    <NotesPanel :project-id="project?.id" :revision-id="noteRevision" :revision-token="noteOpenToken" :refresh-token="noteRefresh" @attach="attachNote" @open-source="emit('openSource',$event)" />
    <ProjectAssistantPanel :project-id="project?.id" :disabled="sending" :note-revision-ids="noteAttachments" @clear-notes="noteAttachments=[]" @notes-changed="noteRefresh++" @open-note="openNote" @sending="assistantSending=$event" @open-source="emit('openSource',$event)" @open-evidence="emit('openEvidence',$event)" />
    <div class="agent-columns">
      <AgentWorkflowForm :project="project" :source="source" :busy="busy" :sending="sending" @start="submit($event)">
        <p v-if="unknown" role="alert">处理结果尚未确认，请先读取状态。同一提交的重发会复用任务标识。</p>
        <button v-if="unknown" type="button" :disabled="sending||loading" @click="retry">显式重发同一提交</button>
        <button type="button" :disabled="!project||loading" @click="refresh()">{{loading?'正在读取…':'刷新任务与处理状态'}}</button>
        <p v-if="error" role="alert">{{error}}</p>
      </AgentWorkflowForm>
      <section class="agent-detail" aria-labelledby="workflow-detail-title"><h2 id="workflow-detail-title">任务记录</h2>
        <p v-if="!loading&&!runs?.items.length">还没有协作任务。</p>
        <div class="agent-run-list"><button v-for="item in runs?.items??[]" :key="item.id" :aria-pressed="selected?.id===item.id" :disabled="sending||unknown" @click="select(item.id)">{{item.kind==='knowledge_pipeline'?'知识整理':'证据问答'}} · {{status[item.status]}} <small>{{new Date(item.created_at).toLocaleString()}}</small></button></div>
        <nav v-if="runs&&runs.total>runs.page_size" aria-label="协作任务分页"><button :disabled="loading||runs.page<=1" @click="refresh(runs.page-1)">上一页</button><span>{{runs.page}}</span><button :disabled="loading||runs.page*runs.page_size>=runs.total" @click="refresh(runs.page+1)">下一页</button></nav>
        <article v-if="selected"><h3>{{status[selected.status]}}</h3><p>模型请求 {{selected.usage.model??0}} · 工具执行 {{selected.usage.tool??0}} · 嵌入请求 {{selected.usage.embedding??0}}</p>
          <section v-if="selected.scope&&(selected.scope.retrieval_mode||selected.scope.include_code_analysis)" class="agent-scope" aria-label="所选任务范围">
            <p v-if="selected.scope.retrieval_mode">检索：{{retrievalLabels[selected.scope.retrieval_mode]}} · {{selected.scope.valid_at?new Date(selected.scope.valid_at).toLocaleString()+`（${timeZone}）`:'当前有效知识'}}</p>
            <p v-if="selected.scope.include_code_analysis">代码分析：{{selected.scope.code_strategy==='semantic'?'编译器静态分析':selected.scope.code_strategy==='tools'?'只读工具 Agent':'单轮候选判断'}}<span v-if="selected.scope.version_ids.length"> · 指定 {{selected.scope.version_ids.length}} 个相关文件版本</span></p>
          </section>
          <AgentCodeResult v-if="selected.result?.code_analysis" :result="selected.result.code_analysis" />
          <p v-if="selected.error_code" role="alert">任务未完成（{{selected.error_code}}）。请核对记录后显式新建任务。</p>
          <div v-if="selected.status==='awaiting_review'" class="agent-review"><p>本次候选：待审核 {{selected.review_counts.pending??0}} · 已确认 {{selected.review_counts.confirmed??0}} · 已拒绝 {{selected.review_counts.rejected??0}}</p>
            <button v-if="selected.source_id" @click="emit('openSource',selected.source_id)">打开原文与候选审核</button><button :disabled="sending||(selected.review_counts.pending??0)>0" @click="resume">审核完成，继续流程</button></div>
          <section v-if="selected.result?.answer" aria-label="协作回答"><h3>回答</h3><AnswerClaims :answer="selected.result.answer" @open-evidence="emit('openEvidence', $event)" /><p v-for="missing in selected.result.answer.missing_information" :key="missing">{{missing}}</p>
            <article v-for="evidence in selected.result.answer.evidence" :key="evidence.id"><strong>{{evidence.title}}</strong><p>{{evidence.quote}}</p><button @click="emit('openEvidence',{source_id:evidence.source_id,chunk_id:evidence.chunk_id})">查看引用原文</button></article></section>
          <AgentRunTrace :events="selected.events" />
        </article>
      </section>
    </div>
  </main>
</template>

<style scoped>
.agent-context,.agent-scope{min-width:0;padding:12px;margin:14px 0;border-left:2px solid var(--line,#c9d5d7);background:#edf3f3}.agent-context label{overflow-wrap:anywhere}.agent-context select{width:100%;min-width:0}.agent-context span{font-size:12px;color:#435e64}
.agent-context{max-height:360px;overflow:auto}
.agent-workspace{height:calc(100% - 104px);overflow:auto;padding:28px 32px;background:#edf3f3;color:var(--ink)}header{display:flex;justify-content:space-between;gap:24px;align-items:start}h1{font-size:27px;margin:8px 0}h2{font-size:18px}h3{font-size:15px}.agent-kicker{font-size:11px;color:var(--teal);letter-spacing:.12em}.agent-columns{display:grid;grid-template-columns:minmax(280px,360px) minmax(0,1fr);gap:24px;margin-top:24px}section.agent-create,section.agent-detail{padding:22px;background:var(--paper,#f8fbfb);border:1px solid var(--line,#c9d5d7);min-width:0}label{display:grid;gap:8px;font-size:12px;margin:14px 0}select,input,textarea,button{font:inherit;min-height:38px;padding:9px;border:1px solid #a8bdbf;background:#fff;color:var(--ink);border-radius:4px;max-width:100%}textarea{resize:vertical}button{cursor:pointer;margin:5px 8px 5px 0;font-size:12px}button:disabled,fieldset:disabled{opacity:.6}fieldset{border:0;padding:0;min-width:0}p{font-size:13px;line-height:1.85;overflow-wrap:anywhere}.agent-check{display:flex;align-items:center}.agent-run-list{display:flex;flex-wrap:wrap;gap:6px}.agent-run-list button[aria-pressed=true]{border-color:var(--rose);background:#f7eaf0}small{display:block;margin-top:4px}.agent-events{padding-left:22px;max-height:350px;overflow:auto}.agent-events li{padding:8px;font-size:12px}.agent-events span{margin-left:12px;color:#435e64}.agent-review{padding:14px;border:1px solid #d8a62c;background:#fff9e9}nav{display:flex;align-items:center;gap:10px}@media(max-width:900px){.agent-columns{grid-template-columns:1fr}.agent-workspace{padding:20px}header{flex-wrap:wrap}}
</style>
