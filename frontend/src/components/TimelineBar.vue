<script setup lang="ts">
import type { TimelinePoint } from '../types'

defineProps<{
  points: TimelinePoint[]
  modelValue: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()
</script>

<template>
  <div class="timeline-bar">
    <div class="timeline-caption">
      <span>知识时间线</span>
      <strong>{{ points[modelValue]?.date }}</strong>
    </div>
    <div class="timeline-track">
      <div class="track-line" />
      <button
        v-for="point in points"
        :key="point.value"
        type="button"
        :class="{ active: point.value <= modelValue, current: point.value === modelValue }"
        :style="{ left: `${(point.value / (points.length - 1)) * 100}%` }"
        :aria-label="`${point.date} ${point.label}`"
        @click="emit('update:modelValue', point.value)"
      >
        <i />
        <span>{{ point.label }}</span>
      </button>
    </div>
    <span class="timeline-now">今天</span>
  </div>
</template>
