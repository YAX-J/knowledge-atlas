<script setup lang="ts">
import { computed, onScopeDispose, ref, watch } from 'vue'
import type { ApiProject, ApiProjectList, ApiSource } from '../api/knowledgeAtlas'
import { useAgentRuns } from '../composables/useAgentRuns'
import type { AgentRun, WorkflowInput } from '../api/agents'
import type { EvidenceLocator } from '../types'
import AgentRunTrace from '../components/agent/AgentRunTrace.vue'
import AgentCodeResult from '../components/agent/AgentCodeResult.vue'

const props=defineProps<{project:ApiProject|null;projects:ApiProjectList|null;source:ApiSource|null;runId?:string}>()
const emit=defineEmits<{selectProject:[project:ApiProject];openSource:[sourceId:string];openEvidence:[locator:EvidenceLocator];run:[id:string]}>()
const {runs,selected,loading,sending,unknown,error,busy,refresh,select,submit,resume,retry}=useAgentRuns(()=>props.project?.id)
const kind=ref<WorkflowInput['kind']>('knowledge_pipeline'),question=ref(''),includeCode=ref(false)
const strategy=ref<'single_step'|'tools'|'semantic'>('single_step'),modelLimit=ref(8)
const currentSource=computed(()=>props.source?.project_id===props.project?.id?props.source:null)
const status:Record<AgentRun['status'],string>={running:'正在协作',awaiting_review:'等待人工审核',succeeded:'已完成',failed:'未完成',interrupted:'执行已中断'}
watch(()=>[props.project?.id,props.runId],()=>{if(props.runId&&props.runId!==selected.value?.id)void select(props.runId)},{immediate:true})
watch(selected,value=>{if(value)emit('run',value.id)})
watch(()=>props.project?.id,()=>{question.value='';includeCode.value=false})
function start() {
  const text=question.value.trim()
  if(busy.value||!props.project||kind.value==='knowledge_pipeline'&&!currentSource.value||kind.value==='question_pipeline'&&!text)return
  void submit({kind:kind.value,source_id:kind.value==='knowledge_pipeline'||includeCode.value?currentSource.value?.id:undefined,
    ...(kind.value==='question_pipeline'?{question:text,retrieval_mode:'bm25' as const}:{}),
    include_code_analysis:includeCode.value,code_strategy:strategy.value,model_limit:modelLimit.value})
}
function changeProject(event:Event) {const value=props.projects?.items.find(item=>item.id===(event.target as HTMLSelectElement).value);if(value)emit('selectProject',value)}
const timer=setInterval(()=>{if(selected.value?.status==='running'&&!loading.value&&!sending.value)void refresh()},3000)
onScopeDispose(()=>clearInterval(timer))
</script>

<template>
  <main class="agent-workspace" aria-labelledby="agent-workspace-title">
    <header><div><span class="agent-kicker">Agent / 有证据的协作</span><h1 id="agent-workspace-title">协作任务</h1><p>代码分析、知识候选整理与证据问答共享任务范围。正式知识经过人工审核后入图。</p></div>
      <label>当前项目<select :value="project?.id??''" :disabled="sending" @change="changeProject"><option disabled value="">请选择项目</option><option v-for="item in projects?.items??[]" :key="item.id" :value="item.id">{{item.name}}</option></select></label></header>
    <div class="agent-columns">
      <section class="agent-create" aria-labelledby="new-workflow-title"><h2 id="new-workflow-title">安排一次协作</h2>
        <form @submit.prevent="start"><fieldset :disabled="busy||!project">
          <label>任务<select v-model="kind"><option value="knowledge_pipeline">整理资料为知识候选</option><option value="question_pipeline">检索证据并回答</option></select></label>
          <p v-if="kind==='knowledge_pipeline'">当前资料：<strong>{{currentSource?.relative_path||currentSource?.original_name||'请先在资料库打开一份已解析资料'}}</strong></p>
          <label v-if="kind==='question_pipeline'">问题<textarea v-model="question" maxlength="200" rows="3" required /></label>
          <label v-if="currentSource&&currentSource.source_type!=='markdown'" class="agent-check"><input v-model="includeCode" type="checkbox" />同时分析当前代码文件</label>
          <label v-if="includeCode">代码分析方式<select v-model="strategy"><option value="single_step">单轮候选判断</option><option value="tools">只读工具 Agent</option><option v-if="['java','typescript','tsx','javascript','jsx','go'].includes(currentSource?.source_type??'')" value="semantic">编译器静态分析</option></select></label>
          <label>本次模型请求上限<input v-model.number="modelLimit" type="number" min="0" max="8" required /></label>
          <p>开始会使用后端配置的模型，可能产生费用；最多 8 次模型请求、16 次工具调用。资料整理完成后，请核对候选再继续。</p>
          <button type="submit" :disabled="kind==='knowledge_pipeline'&&currentSource?.status!=='ready'">{{sending?'正在执行…':'开始协作任务'}}</button>
        </fieldset></form>
        <p v-if="unknown" role="alert">处理结果尚未确认，请先读取状态。同一提交的重发会复用任务标识。</p>
        <button v-if="unknown" type="button" :disabled="sending||loading" @click="retry">显式重发同一提交</button>
        <button type="button" :disabled="!project||loading" @click="refresh()">{{loading?'正在读取…':'刷新任务与处理状态'}}</button>
        <p v-if="error" role="alert">{{error}}</p>
      </section>
      <section class="agent-detail" aria-labelledby="workflow-detail-title"><h2 id="workflow-detail-title">任务记录</h2>
        <p v-if="!loading&&!runs?.items.length">还没有协作任务。</p>
        <div class="agent-run-list"><button v-for="item in runs?.items??[]" :key="item.id" :aria-pressed="selected?.id===item.id" :disabled="sending||unknown" @click="select(item.id)">{{item.kind==='knowledge_pipeline'?'知识整理':'证据问答'}} · {{status[item.status]}} <small>{{new Date(item.created_at).toLocaleString()}}</small></button></div>
        <nav v-if="runs&&runs.total>runs.page_size" aria-label="协作任务分页"><button :disabled="loading||runs.page<=1" @click="refresh(runs.page-1)">上一页</button><span>{{runs.page}}</span><button :disabled="loading||runs.page*runs.page_size>=runs.total" @click="refresh(runs.page+1)">下一页</button></nav>
        <article v-if="selected"><h3>{{status[selected.status]}}</h3><p>模型请求 {{selected.usage.model??0}} · 工具执行 {{selected.usage.tool??0}} · 嵌入请求 {{selected.usage.embedding??0}}</p>
          <AgentCodeResult v-if="selected.result?.code_analysis" :result="selected.result.code_analysis" />
          <p v-if="selected.error_code" role="alert">任务未完成（{{selected.error_code}}）。请核对记录后显式新建任务。</p>
          <div v-if="selected.status==='awaiting_review'" class="agent-review"><p>本次候选：待审核 {{selected.review_counts.pending??0}} · 已确认 {{selected.review_counts.confirmed??0}} · 已拒绝 {{selected.review_counts.rejected??0}}</p>
            <button v-if="selected.source_id" @click="emit('openSource',selected.source_id)">打开原文与候选审核</button><button :disabled="sending||(selected.review_counts.pending??0)>0" @click="resume">审核完成，继续流程</button></div>
          <section v-if="selected.result?.answer" aria-label="协作回答"><h3>回答</h3><p>{{selected.result.answer.answer}}</p><p v-for="missing in selected.result.answer.missing_information" :key="missing">{{missing}}</p>
            <article v-for="evidence in selected.result.answer.evidence" :key="evidence.id"><strong>{{evidence.title}}</strong><p>{{evidence.quote}}</p><button @click="emit('openEvidence',{source_id:evidence.source_id,chunk_id:evidence.chunk_id})">查看引用原文</button></article></section>
          <AgentRunTrace :events="selected.events" />
        </article>
      </section>
    </div>
  </main>
</template>

<style scoped>
.agent-workspace{height:calc(100% - 104px);overflow:auto;padding:28px 32px;background:#edf3f3;color:var(--ink)}header{display:flex;justify-content:space-between;gap:24px;align-items:start}h1{font-size:27px;margin:8px 0}h2{font-size:18px}h3{font-size:15px}.agent-kicker{font-size:11px;color:var(--teal);letter-spacing:.12em}.agent-columns{display:grid;grid-template-columns:minmax(280px,360px) minmax(0,1fr);gap:24px;margin-top:24px}section.agent-create,section.agent-detail{padding:22px;background:var(--paper,#f8fbfb);border:1px solid var(--line,#c9d5d7);min-width:0}label{display:grid;gap:8px;font-size:12px;margin:14px 0}select,input,textarea,button{font:inherit;min-height:38px;padding:9px;border:1px solid #a8bdbf;background:#fff;color:var(--ink);border-radius:4px;max-width:100%}textarea{resize:vertical}button{cursor:pointer;margin:5px 8px 5px 0;font-size:12px}button:disabled,fieldset:disabled{opacity:.6}fieldset{border:0;padding:0;min-width:0}p{font-size:13px;line-height:1.85;overflow-wrap:anywhere}.agent-check{display:flex;align-items:center}.agent-run-list{display:flex;flex-wrap:wrap;gap:6px}.agent-run-list button[aria-pressed=true]{border-color:var(--rose);background:#f7eaf0}small{display:block;margin-top:4px}.agent-events{padding-left:22px;max-height:350px;overflow:auto}.agent-events li{padding:8px;font-size:12px}.agent-events span{margin-left:12px;color:#435e64}.agent-review{padding:14px;border:1px solid #d8a62c;background:#fff9e9}nav{display:flex;align-items:center;gap:10px}@media(max-width:900px){.agent-columns{grid-template-columns:1fr}.agent-workspace{padding:20px}header{flex-wrap:wrap}}
</style>
