<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useNotes } from '../../composables/useNotes'
import { snapshotNote } from '../../api/notes'
const props=defineProps<{projectId?:string;revisionId?:string;revisionToken?:number;refreshToken?:number;analysisBusy?:boolean;analyzing?:boolean}>()
const emit=defineEmits<{attach:[id:string];openSource:[id:string];analyze:[id:string]}>()
const panel=ref<HTMLElement|null>(null)
const {items,selected,historical,revisions,title,markdown,loading,saving,unknown,conflict,error,query,page,total,truncated,dirty,blocked,refresh,select,openRevision,save,resolveUnknown,create,retry,reload}=useNotes(()=>props.projectId)
const savedRevision=computed(()=>historical.value??selected.value?.current)
const canAnalyze=computed(()=>!!props.projectId&&!props.analysisBusy&&!blocked.value&&!!savedRevision.value?.markdown.trim())
function analyze(){if(canAnalyze.value&&savedRevision.value)emit('analyze',savedRevision.value.id)}
watch(()=>[props.revisionId,props.revisionToken],async()=>{const id=props.revisionId;if(!id)return;await openRevision(id);await nextTick();if(historical.value?.id===id){panel.value?.scrollIntoView?.({block:'start'});panel.value?.querySelector<HTMLElement>('h3')?.focus({preventScroll:true})}})
watch(()=>props.refreshToken,()=>void refresh())
async function snapshot(){const project=props.projectId,revision=historical.value??selected.value?.current;if(!project||!revision)return;try{const result=await snapshotNote(project,revision.id);if(props.projectId===project)emit('openSource',result.source_id)}catch(cause){if(props.projectId===project)error.value=cause instanceof Error?cause.message:'快照创建失败'}}
</script>
<template>
  <section ref="panel" class="notes-panel" aria-label="项目笔记">
    <header><div><h2>项目笔记</h2><p>记录技术决策和实践，再让 Agent 从已保存的版本提取知识。</p></div><button :disabled="!projectId||blocked" @click="create()">新建笔记</button></header>
    <div class="notes-layout"><aside><form aria-label="搜索项目笔记" @submit.prevent="page=1;refresh()"><label>搜索笔记<input v-model="query" maxlength="200" /></label><button :disabled="!projectId||loading">搜索</button></form>
      <p v-if="!items.length&&!loading">暂无匹配笔记。</p><p v-if="truncated">搜索已达扫描上限，请缩小范围。</p>
      <div class="note-list"><button v-for="item in items" :key="item.id" :disabled="blocked" :aria-pressed="selected?.id===item.id" @click="select(item.id)">{{item.title}}<small>{{item.origin==='assistant'?'Agent 草稿':'个人笔记'}} · {{item.current_revision_id.slice(0,8)}}</small></button></div>
      <nav v-if="total>20" aria-label="笔记分页"><button :disabled="page<=1||loading" @click="page--;refresh()">上一页</button><span>{{page}}</span><button :disabled="page*20>=total||loading" @click="page++;refresh()">下一页</button></nav>
    </aside><article>
      <p v-if="saving" role="status">正在保存修订…</p><p v-else-if="selected&&!historical&&!dirty&&!unknown&&!conflict" role="status">已保存 · 修订 {{selected.current.number}}</p>
      <p v-if="error" role="alert">{{error}}</p>
      <div v-if="unknown" role="alert"><p>保存结果尚未确认。刷新只读取，不会重新提交。</p><button @click="resolveUnknown">读取本次修订结果</button><button @click="retry">显式重发同一保存</button></div>
      <div v-if="conflict" role="alert"><p>自动保存已暂停；当前草稿已保留。请复制草稿后重新载入最新修订进行比对。</p><button @click="reload">放弃本地草稿并载入最新修订</button></div>
      <template v-if="historical"><h3 tabindex="-1">历史修订 {{historical.number}} · {{historical.title}}</h3><p>修订 {{historical.id}} · {{historical.content_sha256.slice(0,12)}}</p><pre>{{historical.markdown}}</pre><button @click="historical=null">返回编辑器</button></template>
      <template v-else-if="selected"><label>笔记标题<input v-model="title" maxlength="120" :disabled="unknown||conflict" /></label><label>Markdown 正文<textarea v-model="markdown" rows="10" maxlength="60000" :disabled="unknown||conflict" /></label>
        <button :disabled="!dirty||saving||unknown||conflict||!title.trim()" @click="save()">立即保存</button>
        <details v-if="Object.keys(selected.current.provenance).length"><summary>草稿原始引用与来源记录</summary><pre>{{JSON.stringify(selected.current.provenance,null,2)}}</pre></details>
        <details><summary>修订历史</summary><button v-for="revision in revisions" :key="revision.id" :disabled="blocked" @click="openRevision(revision.id)">修订 {{revision.number}} · {{new Date(revision.created_at).toLocaleString()}}</button></details>
      </template><p v-else-if="!historical">选择一份笔记，或新建笔记开始记录。</p>
      <div v-if="savedRevision">
        <p id="note-analysis-help">分析会将此修订的原文分块发送至 DeepSeek。确认候选后，知识才会进入图谱。</p>
        <button class="note-analyze" :disabled="!canAnalyze" aria-describedby="note-analysis-help" @click="analyze">分析笔记并提取知识</button>
        <button :disabled="dirty||saving||unknown||conflict" @click="emit('attach',savedRevision.id)">将此修订附加到助手</button>
        <button :disabled="dirty||saving||unknown||conflict" @click="snapshot">创建固定资料快照</button>
      </div>
      <p v-if="analyzing" role="status">Agent 正在分析笔记…</p>
    </article></div>
  </section>
</template>
<style scoped>
.note-analyze{background:var(--ink,#183b3c);color:#fff;border-color:var(--ink,#183b3c)}
.notes-panel{margin:24px 0;padding:22px;background:var(--paper,#f8fbfb);border:1px solid var(--line,#c9d5d7);border-top:3px solid #b38a33;min-width:0;color:var(--ink)}header{display:flex;justify-content:space-between;gap:16px}h2{font-size:20px}.notes-layout{display:grid;grid-template-columns:minmax(180px,260px) minmax(0,1fr);gap:24px}.notes-layout>*{min-width:0}label{display:grid;gap:7px;margin:10px 0;font-size:13px}input,textarea{box-sizing:border-box;width:100%;font:inherit;padding:9px;border:1px solid #a8bdbf;background:#fff;color:inherit}textarea{resize:vertical;max-height:500px;overflow:auto}p,small{font-size:12px;line-height:1.8;overflow-wrap:anywhere}small{display:block}button{font:inherit;font-size:12px;min-height:36px;padding:8px 10px;margin:5px 8px 5px 0;max-width:100%;overflow-wrap:anywhere;border:1px solid #a8bdbf;background:#fff;color:inherit;cursor:pointer}button:disabled{opacity:.6}button:focus-visible,input:focus-visible,textarea:focus-visible,summary:focus-visible{outline:2px solid var(--rose,#a75870);outline-offset:3px}.note-list{max-height:300px;overflow:auto}.note-list button{display:block;width:100%;text-align:left}.note-list [aria-pressed=true]{border-color:var(--rose);background:#f7eaf0}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:400px;overflow:auto;background:#edf3f3;padding:12px;font-size:12px}details{margin:12px 0}summary{cursor:pointer}@media(max-width:900px){.notes-layout{grid-template-columns:1fr}}
</style>
