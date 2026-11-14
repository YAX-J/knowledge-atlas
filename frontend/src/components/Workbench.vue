<script setup lang="ts">
import type { ApiProject, ApiProjectList } from '../api/knowledgeAtlas'
import type { ProjectOverview } from '../types'
const props = defineProps<{ project: ApiProject | null; projects: ApiProjectList | null; overview: ProjectOverview | null; loading: boolean; error: string }>()
const emit = defineEmits<{ navigate: [value: string]; selectProject: [value: ApiProject]; refresh: [] }>()
function choose(event: Event) { const item = props.projects?.items.find(item => item.id === (event.target as HTMLSelectElement).value); if (item) emit('selectProject', item) }
</script>

<template>
  <main class="workbench-page" aria-labelledby="workbench-title">
    <header class="workbench-heading"><div><p class="workbench-context">个人开发知识工作台</p><h1 id="workbench-title">{{ project?.name ?? '从一个项目开始' }}</h1><p>{{ project?.description || '把笔记、代码和开发记录整理成有证据、有来历的知识。' }}</p></div><label>当前项目<select :value="project?.id ?? ''" @change="choose"><option value="" disabled>选择项目</option><option v-for="item in projects?.items ?? []" :key="item.id" :value="item.id">{{ item.name }}</option></select></label></header>
    <div v-if="error" role="alert" class="workbench-error"><p>{{ error }}</p><button @click="emit('refresh')">重新读取工作台</button></div>
    <p v-if="loading" role="status">正在读取项目进度…</p>
    <section class="workbench-map" aria-label="知识沉淀流程">
      <article><span class="step-number">1</span><div><h2>从技术笔记开始</h2><p>写下你的技术决策和实践，保存后交给 Agent 分析。</p><dl><dt>资料 / 已解析</dt><dd>{{ overview?.sources ?? '—' }} / {{ overview?.ready_sources ?? '—' }}</dd></dl><button class="primary" @click="emit('navigate', 'agents')">打开项目笔记</button><button @click="emit('navigate', 'sources')">打开资料库</button></div></article>
      <article><span class="step-number">2</span><div><h2>核对与沉淀</h2><p>查看抽取候选及原文，确认实体和关系，建立可信知识。</p><dl><dt>待审核候选</dt><dd>{{ overview?.pending_reviews ?? '—' }}</dd></dl><button @click="emit('navigate', 'review')">继续审核知识</button></div></article>
      <article><span class="step-number">3</span><div><h2>关联与回忆</h2><p>沿图谱核对决策，查看演化历史，带着证据继续提问。</p><dl><dt>当前实体 / 关系</dt><dd>{{ overview?.entities ?? '—' }} / {{ overview?.relationships ?? '—' }}</dd></dl><button @click="emit('navigate', 'graph')">浏览真实图谱</button></div></article>
    </section>
    <section class="workbench-bottom"><div class="workbench-recall"><h2>回到上次的思考</h2><p>会话保留问题、回答和证据。追问使用最近上下文，并重新检索项目原文。</p><button class="primary" @click="emit('navigate', 'conversations')">打开证据会话</button><button @click="emit('navigate', 'search')">检索已确认知识</button></div><aside><h2>整理当前知识</h2><p>为同一概念添加别名、核对重复身份，或撤回已经过期的结论。历史仍可回查。</p><button @click="emit('navigate', 'govern')">检查与整理</button><p v-if="overview?.pending_tasks">还有 {{ overview.pending_tasks }} 个任务等待完成，可在资料库查看进度。</p></aside></section>
    <footer><button @click="emit('navigate', 'projects')">管理项目</button><button @click="emit('navigate', 'demo')">查看独立演示图谱</button><span>此工作台只展示项目真实数据。</span></footer>
  </main>
</template>

<style scoped>
.workbench-page { height:calc(100% - 104px);overflow:auto;padding:38px max(32px,calc((100vw - 1260px)/2)) 60px;background:linear-gradient(transparent 23px,#c9d5d71f 24px),linear-gradient(90deg,transparent 23px,#c9d5d71f 24px),#edf3f3;background-size:24px 24px; }
.workbench-heading { display:flex;justify-content:space-between;gap:32px;align-items:end;margin-bottom:38px; }.workbench-context { color:var(--teal);font-size:13px; }h1 { font:550 32px 'Segoe UI Variable Display','Microsoft YaHei',sans-serif;letter-spacing:-.03em;margin:12px 0;overflow-wrap:anywhere; }p { color:#435e64;line-height:1.9;font-size:13px;max-width:72ch; }label { display:grid;gap:8px;min-width:210px;font-size:12px; }select,button { font:inherit;min-height:40px;border:1px solid #a8bdbf;border-radius:4px;padding:9px 14px;background:#f8fbfb;color:var(--ink); }button { cursor:pointer;font-size:13px; }button:hover { border-color:var(--teal);background:var(--teal-soft); }
.workbench-map { display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:1px solid #b9cdcf;background:#f8fbfb; }.workbench-map article { display:flex;gap:16px;min-width:0;padding:28px 24px;border-right:1px solid #c9d5d7; }.workbench-map article:last-child { border:0; }.step-number { display:grid;place-items:center;align-self:start;min-width:28px;height:28px;border:1px solid var(--teal);border-radius:50%;color:var(--teal);font-size:13px; }h2 { font-size:19px;font-weight:600;margin:2px 0 16px; }.workbench-map p { min-height:75px; }.workbench-map dl { display:flex;justify-content:space-between;gap:12px;align-items:baseline;margin:22px 0;padding-top:18px;border-top:1px solid var(--line); }dt { font-size:12px;color:#435e64; }dd { margin:0;font-size:19px;white-space:nowrap; }
.workbench-bottom { display:grid;grid-template-columns:1.5fr 1fr;gap:32px;margin-top:32px; }.workbench-bottom>div,.workbench-bottom>aside { padding:28px;border:1px solid var(--line);background:#f8fbfb; }.workbench-recall { border-left:3px solid var(--teal) !important; }.primary { background:var(--ink);color:white;border-color:var(--ink);margin-right:12px; }.workbench-bottom button { margin-top:14px; }footer { display:flex;gap:20px;align-items:center;flex-wrap:wrap;padding-top:30px;font-size:12px;color:#435e64; }footer button { background:transparent;border:0;padding-left:0;text-decoration:underline; }.workbench-error { padding:16px;border:1px solid #b86782; }
@media(max-width:1000px) { .workbench-map article { padding:20px 14px;gap:10px; }.workbench-bottom { gap:20px; } }
@media(max-width:760px) { .workbench-heading { align-items:start;flex-direction:column; }.workbench-map,.workbench-bottom { grid-template-columns:1fr; }.workbench-map article { border-right:0;border-bottom:1px solid var(--line); }.workbench-map p { min-height:0; }.workbench-page { padding:24px 16px 70px; } }
</style>
