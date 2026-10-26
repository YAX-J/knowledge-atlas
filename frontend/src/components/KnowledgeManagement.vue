<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { FormalKnowledgeNode, IdentityInfo, KnowledgeChangeList, KnowledgeOperation, KnowledgeRetirement, ManagementIntent, Page } from '../types'
const props = defineProps<{
  nodes: FormalKnowledgeNode[]; selected: { id: string; name: string; kind: 'entity' | 'relationship' } | null
  identity: IdentityInfo | null; operations: Page<KnowledgeOperation> | null; retirements: KnowledgeRetirement[]
  changes: KnowledgeChangeList | null; historical: boolean; busy: boolean; loading: boolean; error: string; notice: string
}>()
const emit = defineEmits<{ apply: [input: ManagementIntent]; refresh: [page: number] }>()
const action = ref<'alias' | 'merge' | 'withdraw' | 'reactivate' | 'unmerge' | 'reverse_change' | 'evolution_group'>('alias')
const reason = ref(''), alias = ref(''), target = ref(''), closedTarget = ref(''), mergeMember = ref(''), changeId = ref('')
const oldIds = ref<string[]>([]), newIds = ref<string[]>([])
const preview = ref<ManagementIntent | null>(null)
const oldNames = computed(() => oldIds.value.map(id => props.nodes.find(item => item.id === id)?.name ?? id))
const newNames = computed(() => newIds.value.map(id => props.nodes.find(item => item.id === id)?.name ?? id))
const merged = computed(() => props.operations?.items.filter(item => item.action === 'merge') ?? [])
const closed = computed(() => [...props.retirements.map(item => ({ id: item.knowledge_id, kind: item.kind, name: item.name })),
  ...(props.operations?.items.filter(item => item.action === 'withdraw').map(item => ({ id: String(item.payload.knowledge_id), kind: String(item.payload.kind) as 'entity' | 'relationship', name: String(item.before.name) })) ?? [])])
const disabled = computed(() => props.busy || props.historical)
const selectedType = computed(() => props.nodes.find(item => item.id === props.selected?.id)?.type)
const previewName = computed(() => {
  if (preview.value?.action === 'reactivate') return closed.value.find(item => item.id === closedTarget.value)?.name
  if (preview.value?.action === 'unmerge') return merged.value.find(item => item.payload.knowledge_id === mergeMember.value)?.before.name
  if (preview.value?.action === 'reverse_change') {
    const item = props.changes?.items.find(value => value.id === changeId.value)
    return item ? `${item.new_entity_name} 替代 ${item.old_entity_name}` : ''
  }
  return props.selected?.name
})
watch(() => [props.selected?.id, props.historical], () => { preview.value = null; alias.value = ''; target.value = '' })
function prepare() {
  if (!reason.value.trim() || disabled.value) return
  const common = { reason: reason.value.trim() }
  if (action.value === 'evolution_group') {
    if (!oldIds.value.length || !newIds.value.length) return
    preview.value = { action: action.value, old_entity_ids: [...oldIds.value], new_entity_ids: [...newIds.value], ...common }
    return
  }
  const selected = action.value === 'reactivate' ? closed.value.find(item => item.id === closedTarget.value) : props.selected
  const id = action.value === 'unmerge' ? mergeMember.value : action.value === 'reverse_change' ? changeId.value : selected?.id
  if (!id) return
  if ((action.value === 'alias' || action.value === 'merge') && selected?.kind !== 'entity') return
  if (action.value === 'alias' && !alias.value.trim() || action.value === 'merge' && !target.value) return
  preview.value = { action: action.value, kind: selected?.kind ?? 'entity', knowledge_id: id, ...common,
    ...(action.value === 'alias' ? { alias: alias.value.trim() } : {}), ...(action.value === 'merge' ? { target_id: target.value } : {}) }
}
function confirm() { if (preview.value && !disabled.value) { emit('apply', preview.value); preview.value = null } }
</script>

<template>
  <section class="knowledge-management" aria-labelledby="knowledge-management-title">
    <header><div><h2 id="knowledge-management-title" tabindex="-1">身份与生命周期</h2><p>核对证据后整理重复身份，或调整知识当前是否生效。</p></div><button type="button" :disabled="busy || loading" @click="emit('refresh', 1)">刷新操作记录</button></header>
    <p v-if="identity">当前实体别名：{{ identity.aliases.join('、') || '尚无别名' }}；身份成员 {{ identity.member_ids.length }} 个。</p>
    <p v-if="historical">正在查看历史时间，以下操作只在当前视图开放。</p>
    <form @submit.prevent="prepare">
      <fieldset :disabled="disabled || !!preview"><legend>{{ selected ? `已选知识：${selected.name}` : '选择图谱知识后，可进行身份整理与撤回' }}</legend>
        <label>操作<select v-model="action"><option value="alias">添加别名</option><option value="merge">合并到另一实体</option><option value="unmerge">解除身份合并</option><option value="withdraw">撤回确认</option><option value="reactivate">重新启用</option><option value="reverse_change">撤销替代确认</option><option value="evolution_group">分叉或合并替代</option></select></label>
        <label v-if="action === 'alias'">别名<input v-model="alias" maxlength="255" required /></label>
        <label v-if="action === 'merge'">保留的实体<select v-model="target" required><option value="" disabled>请选择保留身份</option><option v-for="item in nodes.filter(item => item.id !== selected?.id && item.type === selectedType)" :key="item.id" :value="item.id">{{ item.name }} / {{ item.type }}</option></select></label>
        <label v-if="action === 'unmerge'">已合并成员<select v-model="mergeMember" required><option value="" disabled>请选择原实体</option><option v-for="item in merged" :key="item.id" :value="String(item.payload.knowledge_id)">{{ item.before.name }}</option></select></label>
        <label v-if="action === 'reactivate'">停用或撤回的知识<select v-model="closedTarget" required><option value="" disabled>请选择知识</option><option v-for="(item,index) in closed" :key="`${item.id}:${index}`" :value="item.id">{{ item.name }}</option></select></label>
        <label v-if="action === 'reverse_change'">已确认替代<select v-model="changeId" required><option value="" disabled>请选择替代记录</option><option v-for="item in changes?.items.filter(item => item.review_status === 'confirmed' && item.kind === 'SUPERSEDES') ?? []" :key="item.id" :value="item.id">{{ item.new_entity_name }} 替代 {{ item.old_entity_name }}</option></select></label>
        <div v-if="action === 'evolution_group'" class="evolution-selection"><label>旧知识（可多选）<select v-model="oldIds" multiple size="4" required><option v-for="item in nodes" :key="item.id" :value="item.id">{{ item.name }} / {{ item.type }}</option></select></label><label>新知识（可多选）<select v-model="newIds" multiple size="4" required><option v-for="item in nodes" :key="item.id" :value="item.id">{{ item.name }} / {{ item.type }}</option></select></label></div>
        <label>核对理由<textarea v-model="reason" required maxlength="2000" rows="2" /></label><button type="submit">核对操作预览</button>
      </fieldset>
      <div v-if="preview" class="operation-preview" role="group" aria-label="知识操作最终确认"><strong>请确认本次整理</strong><p v-if="preview.action === 'evolution_group'">{{ oldNames.join('、') }} 将由 {{ newNames.join('、') }} 替代。</p><p v-else>目标：{{ previewName || '所选历史记录' }}<span v-if="preview.action === 'merge'"> → {{ nodes.find(item => item.id === target)?.name }}</span>；操作：{{ { alias:'添加别名', merge:'合并身份', unmerge:'解除合并', withdraw:'撤回确认', reactivate:'重新启用', reverse_change:'撤销替代' }[preview.action] }}。</p><p>{{ preview.reason }}</p><p>原始审核和证据继续保留，变化从当前时刻生效。</p><button type="button" :disabled="disabled" @click="confirm">确认执行</button><button type="button" :disabled="busy" @click="preview = null">返回修改</button></div>
    </form>
    <p v-if="error" role="alert">{{ error }}</p><p v-if="notice" role="status">{{ notice }}</p>
    <details><summary>查看操作审计（{{ operations?.total ?? 0 }}）</summary><div class="operation-log" tabindex="0"><article v-for="item in operations?.items ?? []" :key="item.id"><strong>{{ item.action }} · {{ new Date(item.created_at).toLocaleString() }}</strong><p>{{ item.reason }}</p><details><summary>前后快照</summary><pre>{{ JSON.stringify({ before: item.before, after: item.after }, null, 2) }}</pre></details></article></div><nav v-if="operations && operations.total > operations.page_size" aria-label="操作审计分页"><button :disabled="loading || operations.page <= 1" @click="emit('refresh', operations.page - 1)">上一页</button><span>{{ operations.page }}</span><button :disabled="loading || operations.page * operations.page_size >= operations.total" @click="emit('refresh', operations.page + 1)">下一页</button></nav></details>
  </section>
</template>

<style scoped>
.knowledge-management { margin-top: 24px; padding: 22px; border: 1px solid var(--line); border-radius: 4px; background: #f8fbfb; font-size: 13px; }header { display:flex;align-items:start;justify-content:space-between;gap:20px; }h2 { margin:0;font-size:19px; }p { line-height:1.8;color:#435e64;overflow-wrap:anywhere; }fieldset { display:flex;align-items:end;flex-wrap:wrap;gap:14px;border:0;padding:10px 0; }legend { padding:12px 0;font-weight:600; }label { display:grid;gap:7px;min-width:160px;flex:1; }label:has(textarea) { flex-basis:100%; }select,input,textarea,button { font:inherit;color:var(--ink);border:1px solid #9ab0b3;background:white;border-radius:4px;padding:9px;max-width:100%; }button { cursor:pointer;min-height:38px; }button:disabled { opacity:.5;cursor:not-allowed; }.evolution-selection { display:flex;flex-basis:100%;gap:20px; }.operation-preview { padding:18px;border:1px solid var(--rose);background:#f7edf1; }.operation-preview button { margin:8px 10px 0 0; }.operation-log { max-height:330px;overflow:auto;margin-top:14px; }.operation-log article { padding:14px;border-top:1px solid var(--line); }pre { white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px; }nav { display:flex;align-items:center;gap:12px;margin-top:16px; }
</style>
