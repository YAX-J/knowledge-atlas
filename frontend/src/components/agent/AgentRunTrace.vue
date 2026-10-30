<script setup lang="ts">
import type {AgentEvent} from '../../api/agents'
defineProps<{events:AgentEvent[]}>()
const agents:Record<string,string>={workflow:'协调流程',code_analysis:'代码分析',knowledge_extraction:'知识候选整理',evidence_qa:'证据问答'}
const kinds:Record<string,string>={model:'模型请求',tool:'工具执行',embedding:'嵌入请求',agent:'专业任务',workflow:'协调流程',human_review:'人工审核',
  code_checkpoint:'代码分析结果',extraction_checkpoint:'候选整理结果',answer_checkpoint:'证据回答结果'}
const states:Record<string,string>={started:'开始',ok:'完成',succeeded:'完成',saved:'已保存',failed:'失败',error:'参数或范围被拒绝',awaiting_review:'等待审核'}
const tools:Record<string,string>={read_chunk:'阅读原文分块',read_evidence:'核对引用',search_knowledge:'检索正式知识',read_source_range:'阅读源码行',get_imports:'查看导入',search_symbols:'搜索符号',find_references:'查找引用',get_type_members:'查看成员',not_allowed:'未授权工具'}
</script>
<template><section aria-labelledby="agent-events-title"><h3 id="agent-events-title">执行事件</h3><ol class="agent-events"><li v-for="event in events" :key="event.sequence"><strong>{{agents[event.agent]??event.agent}}</strong><span>{{kinds[event.kind]??event.kind}} · {{states[event.status]??event.status}}<template v-if="event.tool_name"> · {{tools[event.tool_name]??'只读工具'}}</template></span></li></ol></section></template>
<style scoped>.agent-events{padding-left:22px;max-height:350px;overflow:auto}.agent-events li{padding:8px;font-size:12px}.agent-events span{margin-left:12px;color:#435e64}h3{font-size:15px}</style>
