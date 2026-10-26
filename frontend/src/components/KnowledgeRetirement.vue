<script setup lang="ts">
import { ref, watch } from 'vue'
import type { KnowledgeRetirement, RetirementInput, RetirementList } from '../types'

const props = defineProps<{
  selected: { kind: 'entity' | 'relationship'; id: string; name: string; current: boolean } | null
  records: RetirementList | null; loading: boolean; error: string; actionError: string; notice: string
  busy: boolean; historical: boolean
}>()
const emit = defineEmits<{
  retire: [input: RetirementInput]; page: [page: number]; visit: [event: KnowledgeRetirement]
}>()
const category = ref<'correction' | 'obsolete'>('correction'), reason = ref(''), confirming = ref(false)
watch(() => [props.selected?.id, props.selected?.kind, props.historical], () => { reason.value = ''; confirming.value = false })
function submit() {
  if (!props.selected?.current || props.busy || props.historical || !reason.value.trim()) return
  if (!confirming.value) { confirming.value = true; return }
  emit('retire', { kind:props.selected.kind, knowledge_id:props.selected.id, category:category.value, reason:reason.value.trim() })
}
</script>

<template>
  <section class="retirement" aria-label="知识纠错与停用">
    <h2>知识纠错与停用</h2>
    <p>误确认或已过期的知识可从现在起停用。保留原确认、证据和历史，不自动改写结论；正确内容应重新经候选审核确认。</p>
    <p v-if="notice" role="status">{{ notice }}</p>
    <p v-if="actionError" role="alert">{{ actionError }} 请先刷新停用记录核对结果。</p>
    <form v-if="selected?.current && !historical" @submit.prevent="submit">
      <p>将停用：<strong>{{ selected.name }}</strong>（{{ selected.kind === 'entity' ? '实体；关联关系也会退出当前视图' : '关系' }}）</p>
      <label>停用原因<select v-model="category" :disabled="busy" @change="confirming = false"><option value="correction">误确认，需要纠错</option><option value="obsolete">已过期，不再适用</option></select></label>
      <label>核对说明<textarea v-model="reason" required maxlength="2000" rows="3" :disabled="busy" @input="confirming = false" /></label>
      <p v-if="confirming">确认从现在起停用？此次操作会记录说明与前后快照，当前版本不提供恢复按钮。</p>
      <button type="submit" :disabled="busy || !reason.trim()">{{ busy ? '正在提交…' : confirming ? '确认停用此项知识' : '核对停用影响' }}</button>
      <button v-if="confirming" type="button" :disabled="busy" @click="confirming = false">取消停用</button>
    </form>
    <p v-else>{{ historical ? '历史视图只读；返回当前时间后可停用有效知识。' : '请选择一条当前有效知识以核对并停用。' }}</p>
    <h3>停用记录 <button type="button" :disabled="busy || loading" @click="emit('page', records?.page ?? 1)">刷新停用记录</button></h3>
    <p v-if="loading" role="status">正在读取停用记录…</p>
    <p v-else-if="error" role="alert">{{ error }}</p>
    <p v-else-if="!records?.items.length">尚无停用记录。</p>
    <div v-else class="records" role="region" aria-label="知识停用记录滚动区域" tabindex="0">
      <article v-for="event in records.items" :key="event.id">
        <strong>{{ event.name }} · {{ event.category === 'correction' ? '误确认纠错' : '过期停用' }}</strong>
        <p>{{ event.reason }}</p><small>{{ new Date(event.effective_at).toLocaleString('zh-CN') }}</small>
        <button type="button" :disabled="busy" @click="emit('visit', event)">查看停用前知识</button>
        <details><summary>查看审计快照</summary><pre>{{ JSON.stringify({ before:event.before, after:event.after }, null, 2) }}</pre></details>
      </article>
    </div>
    <nav v-if="records && records.total > records.page_size" aria-label="停用记录分页">
      <button type="button" :disabled="busy || loading || records.page <= 1" @click="emit('page', records.page - 1)">上一页</button>
      <span>第 {{ records.page }} 页 / {{ records.total }} 条</span>
      <button type="button" :disabled="busy || loading || records.page * records.page_size >= records.total" @click="emit('page', records.page + 1)">下一页</button>
    </nav>
  </section>
</template>

<style scoped>
.retirement { margin-top: 24px; padding: 22px; border: 1px solid var(--line); border-radius: 7px; background: var(--paper); overflow-wrap: anywhere; }
h2 { font: 500 23px "Noto Serif SC", SimSun, serif; margin: 0; } h3 { font-size: 15px; } p, small { color: #405d63; font-size: 12px; line-height: 1.9; }
form { max-width: 720px; } label { display: grid; gap: 7px; margin: 12px 0; font-size: 12px; } button, select, textarea { font: inherit; font-size: 12px; color: var(--ink); background: #f8fbfb; border: 1px solid #aabec0; border-radius: 5px; min-height: 40px; padding: 9px 12px; box-sizing: border-box; } textarea { width: 100%; resize: vertical; } button { cursor: pointer; margin: 4px 8px 4px 0; } button:disabled { opacity: .5; cursor: not-allowed; }
button:focus-visible, select:focus-visible, textarea:focus-visible, summary:focus-visible, [tabindex]:focus-visible { outline: 2px solid var(--rose); outline-offset: 3px; } .records { max-height: 420px; overflow: auto; } article { border-top: 1px solid var(--line); padding: 16px 0; font-size: 13px; } pre { white-space: pre-wrap; max-height: 260px; overflow: auto; font-size: 11px; } summary { cursor: pointer; } nav { display: flex; gap: 12px; align-items: center; font-size: 12px; }
</style>
