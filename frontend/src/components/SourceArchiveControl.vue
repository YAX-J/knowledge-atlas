<script setup lang="ts">
import { onScopeDispose, ref } from 'vue'
import { archiveSource } from '../api/library'
const props=defineProps<{projectId:string;sourceId:string;archived:boolean;locked:boolean}>()
const emit=defineEmits<{changed:[];busy:[value:boolean]}>()
const reason=ref(''),busy=ref(false),error=ref('')
let disposed=false
onScopeDispose(()=>{disposed=true;if(busy.value)emit('busy',false)})
async function submit() {
 if(busy.value||props.locked||!reason.value.trim())return
 busy.value=true;emit('busy',true);error.value=''
 try { await archiveSource(props.projectId,props.sourceId,!props.archived,reason.value.trim());if(!disposed){reason.value='';emit('changed')} }
 catch(value) { if(!disposed)error.value=value instanceof Error?value.message:'操作未确认，请刷新资料状态。' }
 finally { if(!disposed){busy.value=false;emit('busy',false)} }
}
</script>
<template>
 <details class="source-archive-control"><summary>{{ archived?'已归档资料：恢复到资料库':'归档此资料' }}</summary>
 <p>归档只调整资料库和默认代码搜索，不删除原文、不撤回已确认知识；历史证据和固定快照仍可读取。</p>
 <form @submit.prevent="submit"><label>归档或恢复原因<input v-model="reason" maxlength="2000" required :disabled="busy||locked" /></label><button type="submit" :disabled="busy||locked||!reason.trim()">{{ archived?'恢复资料':'归档资料' }}</button></form><p v-if="error" role="alert">{{ error }}</p>
 </details>
</template>
<style scoped>
.source-archive-control { padding:10px 0;overflow-wrap:anywhere; }summary { cursor:pointer;font-size:13px;font-weight:600; }p { font-size:12px;line-height:1.7; }form { display:flex;gap:8px;align-items:end;flex-wrap:wrap; }label { display:grid;gap:5px;font-size:12px; }input,button { min-height:36px;box-sizing:border-box;padding:6px 10px;border:1px solid var(--line);border-radius:5px;background:white;color:var(--ink); }input { width:260px;max-width:100%; }button { cursor:pointer; }[role=alert] { color:var(--rose); }input:focus-visible,button:focus-visible,summary:focus-visible { outline:2px solid var(--teal);outline-offset:2px; }
</style>
