<script setup lang="ts">
import { onScopeDispose, ref, watch } from 'vue'
import type { ApiProject, ApiProjectList } from '../api/knowledgeAtlas'
import { archivedProjects, archiveProject, editProject } from '../api/library'
const props=defineProps<{project:ApiProject|null;locked:boolean}>()
const emit=defineEmits<{updated:[project:ApiProject];busy:[value:boolean]}>()
const name=ref(''),description=ref(''),busy=ref(false),error=ref(''),notice=ref(''),archived=ref<ApiProjectList|null>(null)
let disposed=false,reads=0
onScopeDispose(()=>{disposed=true;reads++;if(busy.value)emit('busy',false)})
watch(()=>props.project,project=>{name.value=project?.name ?? '';description.value=project?.description ?? '';error.value=notice.value=''}, {immediate:true})
async function loadArchived(page=1) {
 const request=++reads
 try { const result=await archivedProjects(page);if(!disposed && request===reads)archived.value=result }
 catch(value) { if(!disposed && request===reads)error.value=value instanceof Error?value.message:'读取归档项目失败' }
}
async function change(action:'edit'|'archive'|'restore',project=props.project) {
 if(!project || busy.value || props.locked)return
 busy.value=true;emit('busy',true);error.value=''
 try {
  const result=action==='edit'?await editProject(project,name.value.trim(),description.value):await archiveProject(project,action==='archive')
  if(disposed)return
  emit('updated',result);notice.value=action==='edit'?'项目已保存。':action==='archive'?'项目已归档，历史数据保留。':'项目已恢复。'
  if(archived.value)await loadArchived(archived.value.page)
 } catch(value) { if(!disposed)error.value=value instanceof Error?value.message:'操作未确认，请刷新项目列表后核对。' }
 finally { if(!disposed){busy.value=false;emit('busy',false)} }
}
</script>
<template>
 <section class="project-management" aria-label="项目编辑与归档">
  <details v-if="project"><summary>编辑与归档当前项目</summary>
   <form @submit.prevent="change('edit')"><label>项目名称<input v-model="name" maxlength="120" required :disabled="busy||locked" /></label><label>项目说明<textarea v-model="description" maxlength="4000" :disabled="busy||locked" /></label><button :disabled="busy||locked||!name.trim()" type="submit">保存项目修改</button><button :disabled="busy||locked" type="button" @click="change('archive')">归档当前项目</button></form>
   <p>归档后项目退出日常列表，保留全部原文和历史，可从下方恢复。运行或待审批任务需要先完成或取消。</p>
  </details>
  <button type="button" :disabled="busy||locked" @click="loadArchived()">查看归档项目</button>
  <ul v-if="archived" aria-label="归档项目"><li v-for="item in archived.items" :key="item.id">{{ item.name }} <button :disabled="busy||locked" type="button" @click="change('restore',item)">恢复项目 {{ item.name }}</button></li></ul>
  <p v-if="archived&&!archived.items.length">没有已归档项目。</p>
  <nav v-if="archived&&archived.total>archived.page_size" aria-label="归档项目分页"><button :disabled="busy||locked||archived.page<=1" @click="loadArchived(archived.page-1)">上一页</button><span>{{ archived.page }}</span><button :disabled="busy||locked||archived.page*archived.page_size>=archived.total" @click="loadArchived(archived.page+1)">下一页</button></nav>
  <p v-if="error" role="alert">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p>
 </section>
</template>
<style scoped>
.project-management { margin:14px 0;padding:14px;border:1px solid var(--line);border-radius:8px;overflow-wrap:anywhere; }summary { cursor:pointer;font-weight:600;margin-bottom:10px; }form { display:flex;gap:12px;align-items:end;flex-wrap:wrap; }label { display:grid;gap:6px;min-width:0;font-size:13px; }input,textarea { width:240px;max-width:100%;box-sizing:border-box;padding:8px;border:1px solid var(--line);border-radius:5px;font:inherit; }button { min-height:36px;padding:7px 12px;border:1px solid var(--line);background:white;border-radius:5px;color:var(--ink);cursor:pointer; }p { font-size:12px;line-height:1.7; }button:focus-visible,input:focus-visible,textarea:focus-visible,summary:focus-visible { outline:2px solid var(--teal);outline-offset:2px; }[role=alert] { color:var(--rose); }ul { max-height:240px;overflow:auto; }li { margin:8px 0; }
</style>
