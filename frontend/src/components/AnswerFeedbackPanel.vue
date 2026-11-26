<script setup lang="ts">
import { onScopeDispose, ref, watch } from 'vue'
import type { QuestionAnswer } from '../types'
import { listFeedback, saveFeedback, type AnswerFeedback, type FeedbackInput } from '../api/library'
const props=defineProps<{projectId:string;turnId:string;answer:QuestionAnswer}>()
const items=ref<AnswerFeedback[]>([]),claim=ref(0),category=ref('incorrect'),comment=ref(''),error=ref(''),notice=ref(''),busy=ref(false),pending=ref<FeedbackInput|null>(null)
const labels:Record<string,string>={incorrect:'事实错误',irrelevant_citation:'引用无关',overstatement:'过度推断',wrong_version:'版本或时间错误',incomplete:'信息不完整'}
let generation=0,disposed=false,reads=0
onScopeDispose(()=>{disposed=true;generation++;reads++})
async function refresh() {
 const captured=generation,request=++reads
 try {
  const result=await listFeedback(props.projectId,props.turnId)
  if(disposed||captured!==generation||request!==reads)return
  items.value=result
  if(pending.value&&result.some(item=>item.id===pending.value?.request_id)){pending.value=null;notice.value='纠错记录已保存。';comment.value=''}
 }catch(value){if(!disposed&&captured===generation&&request===reads)error.value=value instanceof Error?value.message:'读取反馈失败'}
}
watch(()=>[props.projectId,props.turnId],()=>{generation++;items.value=[];pending.value=null;busy.value=false;error.value=notice.value=comment.value='';claim.value=0;void refresh()},{immediate:true})
async function submit() {
 if(busy.value||(!pending.value&&!comment.value.trim()))return
 const captured=generation,project=props.projectId,turn=props.turnId
 pending.value??={request_id:crypto.randomUUID(),claim_index:claim.value,category:category.value,comment:comment.value.trim()}
 busy.value=true;error.value=''
 try {await saveFeedback(project,turn,pending.value);if(disposed||captured!==generation)return;pending.value=null;comment.value='';notice.value='纠错记录已保存，原答案和知识未改写。';await refresh()}
 catch(value){if(!disposed&&captured===generation)error.value=value instanceof Error?value.message:'保存结果未确认，请先刷新；可显式重发同一反馈。'}
 finally{if(!disposed&&captured===generation)busy.value=false}
}
</script>
<template>
 <details class="answer-feedback"><summary>记录结论问题</summary><p>反馈绑定这次已保存回答的精确结论，保留原答案。修改已确认知识需要另行审核。</p>
 <form @submit.prevent="submit"><label>结论<select v-model="claim" :disabled="busy||!!pending"><option v-for="(item,index) in answer.claims??[]" :key="index" :value="index">{{ index+1 }}. {{ item.text.slice(0,70) }}</option></select></label><label>问题类型<select v-model="category" :disabled="busy||!!pending"><option v-for="(label,key) in labels" :key="key" :value="key">{{ label }}</option></select></label><label>纠错说明<textarea v-model="comment" maxlength="2000" required :disabled="busy||!!pending" /></label><button :disabled="busy||(!pending&&!comment.trim())" type="submit">{{ pending?'显式重发同一反馈':'保存纠错记录' }}</button><button type="button" :disabled="busy" @click="refresh">刷新纠错记录</button></form>
 <p v-if="error" role="alert">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p>
 <ul aria-label="已保存纠错记录"><li v-for="item in items" :key="item.id">结论 {{ item.claim_index+1 }} · {{ labels[item.category]??item.category }}：{{ item.comment }}</li></ul><p>最多展示最近 50 条。</p>
 </details>
</template>
<style scoped>
.answer-feedback { margin-top:16px;padding:12px;border:1px solid var(--line);border-radius:6px;overflow-wrap:anywhere; }summary { cursor:pointer;font-weight:600; }form { display:flex;gap:10px;align-items:end;flex-wrap:wrap; }label { display:grid;gap:5px;font-size:12px;max-width:100%; }select,textarea,button { box-sizing:border-box;min-height:36px;max-width:100%;padding:7px;border:1px solid var(--line);border-radius:5px;background:white;color:var(--ink);font:inherit; }select { max-width:320px; }textarea { width:320px; }button { cursor:pointer; }p,li { font-size:12px;line-height:1.8; }ul { max-height:220px;overflow:auto; }[role=alert] { color:var(--rose); }select:focus-visible,textarea:focus-visible,button:focus-visible,summary:focus-visible { outline:2px solid var(--teal);outline-offset:2px; }
</style>
