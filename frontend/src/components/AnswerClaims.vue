<script setup lang="ts">
import type { EvidenceLocator, QuestionAnswer } from '../types'

defineProps<{ answer: QuestionAnswer }>()
const emit = defineEmits<{ openEvidence: [locator: EvidenceLocator] }>()
</script>

<template>
  <section v-if="answer.claims?.length" class="answer-claims" aria-label="逐条结论与引用">
    <p class="claim-notice">引用归属已经校验；引用是否充分支撑结论，仍需核对原文。</p>
    <ol>
      <li v-for="(claim, index) in answer.claims" :key="index" class="answer-claim">
        <span class="claim-status" :class="claim.status">{{ claim.status === 'supported' ? '附有引用' : '证据不足' }}</span>
        <p>{{ claim.text }}</p>
        <div v-if="claim.citation_ids.length" class="claim-citations" :aria-label="`结论 ${index + 1} 的引用`">
          <template v-for="id in claim.citation_ids" :key="id">
            <button v-if="answer.evidence.some(item => item.id === id)" type="button"
              @click="emit('openEvidence', answer.evidence.find(item => item.id === id)!)">
              [{{ answer.evidence.findIndex(item => item.id === id) + 1 }}] 查看原文 · {{ answer.evidence.find(item => item.id === id)!.title }}
            </button>
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
ol { padding-left: 24px; margin: 18px 0; }
.answer-claim { padding: 14px 0; border-bottom: 1px solid var(--line); }
.answer-claim p, .answer-text { white-space: pre-wrap; font-size: 14px; line-height: 1.9; }
.claim-status { display: inline-block; padding: 3px 8px; font-size: 12px; border-radius: 4px; color: #245c4e; background: #dceee7; }
.claim-status.insufficient { color: #805318; background: #f2e8d5; }
.claim-citations { display: flex; flex-wrap: wrap; gap: 8px; font-size: 12px; }
button { max-width: 100%; min-height: 36px; padding: 7px 10px; border: 1px solid #aabec0; border-radius: 4px; background: var(--paper); color: var(--teal); font: inherit; text-align: left; overflow-wrap: anywhere; cursor: pointer; }
button:focus-visible { outline: 2px solid var(--teal); outline-offset: 2px; }
</style>
