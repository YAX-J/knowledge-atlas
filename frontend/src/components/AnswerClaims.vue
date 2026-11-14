<script setup lang="ts">
import { computed } from 'vue'
import type { EvidenceLocator, QuestionAnswer } from '../types'

const props = defineProps<{ answer: QuestionAnswer }>()
const emit = defineEmits<{ openEvidence: [locator: EvidenceLocator] }>()
const timeLabels = { manual: '手动选择', question: '从问题识别', current: '当前', clarification: '待补充', comparison: '切换前后' }
const claims = computed(() => {
  const citations = new Map(props.answer.evidence.map((item, index) => [item.id, { item, position: index + 1 }]))
  return props.answer.claims?.map(claim => ({
    ...claim, citations: claim.citation_ids.map(id => ({ id, ...citations.get(id) })),
  }))
})
</script>

<template>
  <dl v-if="answer.comparison" class="comparison-times" aria-label="实际对比时点">
    <div><dt>对比前</dt><dd><time :datetime="answer.comparison.before_at">{{ new Date(answer.comparison.before_at).toLocaleString('zh-CN') }}</time></dd></div>
    <div><dt>对比后</dt><dd><time :datetime="answer.comparison.after_at">{{ new Date(answer.comparison.after_at).toLocaleString('zh-CN') }}</time></dd></div>
    <div><dt>审核确认的切换时间</dt><dd><time :datetime="answer.comparison.cutover_at">{{ new Date(answer.comparison.cutover_at).toLocaleString('zh-CN') }}</time></dd></div>
  </dl>
  <p v-else-if="answer.time_scope?.valid_at" class="answer-time" aria-label="实际查询时点">
    查询时点 · {{ timeLabels[answer.time_scope.source] }}
    <span v-if="answer.time_scope.expression">「{{ answer.time_scope.expression }}」</span>
    <time :datetime="answer.time_scope.valid_at">{{ new Date(answer.time_scope.valid_at).toLocaleString('zh-CN') }}</time>
  </p>
  <section v-if="claims?.length" class="answer-claims" aria-label="逐条结论与引用">
    <p class="claim-notice">引用归属已经校验；引用是否充分支撑结论，仍需核对原文。</p>
    <ol>
      <li v-for="(claim, index) in claims" :key="`${answer.id}-${index}`" class="answer-claim">
        <span class="claim-status" :class="claim.status">{{ claim.status === 'supported' ? '附有引用' : '证据不足' }}</span>
        <p>{{ claim.text }}</p>
        <div v-if="claim.citation_ids.length" class="claim-citations" :aria-label="`结论 ${index + 1} 的引用`">
          <template v-for="{ id, item, position } in claim.citations" :key="id">
            <template v-if="item">
                  <details v-if="item.relationship" class="citation-relationship">
                    <summary>[{{ position }}] {{ id === answer.comparison?.before_citation_id ? '查看切换前关系' : id === answer.comparison?.after_citation_id ? '查看切换后关系' : '查看支撑关系' }}</summary>
                    <p><strong>{{ item.relationship.source.name }} → {{ item.relationship.target.name }}</strong> · {{ item.relationship.type }}</p>
                    <dl>
                      <div><dt>查询时点</dt><dd><time :datetime="item.relationship.valid_at">{{ new Date(item.relationship.valid_at).toLocaleString('zh-CN') }}</time></dd></div>
                      <div><dt>生效时间</dt><dd><time :datetime="item.relationship.valid_from">{{ new Date(item.relationship.valid_from).toLocaleString('zh-CN') }}</time></dd></div>
                      <div><dt>失效时间</dt><dd><time v-if="item.relationship.valid_to" :datetime="item.relationship.valid_to">{{ new Date(item.relationship.valid_to).toLocaleString('zh-CN') }}</time><span v-else>未指定</span></dd></div>
                    </dl>
                    <blockquote>{{ item.quote }}</blockquote>
                    <button type="button" @click="emit('openEvidence', item)">查看原文 · {{ item.title }}</button>
                  </details>
                  <button v-else type="button" @click="emit('openEvidence', item)">[{{ position }}] 查看原文 · {{ item.title }}</button>
            </template>
            <span v-else role="status">该引用暂不可定位</span>
          </template>
        </div>
      </li>
    </ol>
  </section>
  <div v-else class="legacy-answer">
    <p class="answer-text">{{ answer.answer }}</p>
    <p class="claim-notice">此历史格式未保存逐条引用对应关系，请结合下方引用核对。</p>
  </div>
</template>

<style scoped>
.answer-claims, .legacy-answer { min-width: 0; overflow-wrap: anywhere; }
.claim-notice { color: #536b70; font-size: 12px; line-height: 1.8; }
.answer-time { color: #375960; font-size: 13px; line-height: 1.8; overflow-wrap: anywhere; }
.answer-time time { margin-left: 6px; }
.comparison-times { display: flex; flex-wrap: wrap; gap: 8px 24px; font-size: 13px; color: #375960; }
.comparison-times div { min-width: 0; overflow-wrap: anywhere; }
.comparison-times dd { margin: 4px 0 0; }
ol { padding-left: 24px; margin: 18px 0; }
.answer-claim { padding: 14px 0; border-bottom: 1px solid var(--line); }
.answer-claim p, .answer-text { white-space: pre-wrap; font-size: 14px; line-height: 1.9; }
.claim-status { display: inline-block; padding: 3px 8px; font-size: 12px; border-radius: 4px; color: #245c4e; background: #dceee7; }
.claim-status.insufficient { color: #805318; background: #f2e8d5; }
.claim-citations { display: flex; flex-wrap: wrap; gap: 8px; font-size: 12px; }
button { max-width: 100%; min-height: 36px; padding: 7px 10px; border: 1px solid #aabec0; border-radius: 4px; background: var(--paper); color: var(--teal); font: inherit; text-align: left; overflow-wrap: anywhere; cursor: pointer; }
button:focus-visible, summary:focus-visible { outline: 2px solid var(--teal); outline-offset: 2px; }
.citation-relationship { width: 100%; max-width: 100%; box-sizing: border-box; padding: 10px 12px; border: 1px solid #aabec0; border-radius: 5px; background: var(--paper); }
.citation-relationship summary { cursor: pointer; color: var(--teal); }
.citation-relationship dl { margin: 10px 0; }
.citation-relationship dl div { display: flex; flex-wrap: wrap; gap: 4px 12px; }
.citation-relationship dd { margin: 0; }
.citation-relationship blockquote { margin: 10px 0; padding-left: 10px; border-left: 2px solid #aabec0; }
</style>
