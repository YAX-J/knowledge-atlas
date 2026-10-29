<script setup lang="ts">
import type {AgentCallAnalysis} from '../../api/knowledgeAtlas'
defineProps<{result:AgentCallAnalysis}>()
</script>
<template><section aria-label="协作代码分析"><h3>代码分析依据</h3><p>扫描 {{result.scanned_source_count}} 份文件 · {{result.calls.length}} 个已分析调用 · 未覆盖 {{result.uncovered_call_count??0}} 个</p><p>{{result.context?.commit_sha?`固定提交 ${result.context.commit_sha}`:'本地所选文件版本'}}<span v-if="result.truncated"> · 范围达到上限，结果不完整</span></p><details><summary>查看调用定位</summary><article v-for="call in result.calls" :key="call.id"><strong>{{call.callee_name}}</strong><p>第 {{call.line}} 行 · {{call.resolution}}</p><pre>{{call.call_quote}}</pre></article></details></section></template>
<style scoped>p{font-size:13px;line-height:1.8;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}article{border-bottom:1px solid #c9d5d7;padding:12px 0}h3{font-size:15px}</style>
