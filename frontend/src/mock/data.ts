import type { Evidence, KnowledgeEdge, KnowledgeNode, NodeType, TimelinePoint } from '../types'

export const nodeTypeLabels: Record<NodeType, string> = {
  project: '项目',
  concept: '技术概念',
  pattern: '设计模式',
  decision: '技术决策',
  note: '知识笔记',
  question: '开放问题',
  code: '代码实体',
}

export const nodes: KnowledgeNode[] = [
  {
    id: 'event-driven', label: '事件驱动架构', subtitle: '2 LINKS · 3 SOURCES', type: 'concept',
    x: 500, y: 390, size: 72, confidence: 0.96, validFrom: '2024-05', project: '订单状态机',
    description: '围绕事件产生、传递和消费组织系统组件的架构方式。你在三个项目决策和两段代码中使用了它。',
    evidenceIds: ['event-note', 'domain-event', 'adr-006'],
  },
  {
    id: 'order-state', label: '订单状态机', subtitle: 'PROJECT', type: 'project',
    x: 315, y: 270, size: 70, confidence: 0.92, validFrom: '2024-05', project: '订单状态机',
    description: '负责订单生命周期编排的核心项目，包含支付、履约和异常补偿流程。',
    evidenceIds: ['event-note', 'domain-event'],
  },
  {
    id: 'domain-event', label: 'DomainEvent', subtitle: 'CODE ENTITY', type: 'code',
    x: 410, y: 150, size: 62, confidence: 0.98, validFrom: '2024-05', project: '订单状态机',
    description: '领域事件抽象接口，统一定义事件编号、发生时间与聚合根标识。',
    evidenceIds: ['domain-event'],
  },
  {
    id: 'spring-tx', label: 'Spring Transaction', subtitle: 'TECHNOLOGY', type: 'note',
    x: 645, y: 135, size: 58, confidence: 0.86, validFrom: '2024-08', project: '订单状态机',
    description: 'Spring 的声明式事务机制，用于保证本地数据库状态变更的一致性。',
    evidenceIds: ['event-note'],
  },
  {
    id: 'kafka', label: 'Kafka 消费语义', subtitle: 'CONCEPT', type: 'concept',
    x: 715, y: 260, size: 58, confidence: 0.91, validFrom: '2024-08', project: '消息中心',
    description: '消息至少一次投递下的消费确认、重复处理与失败重试语义。',
    evidenceIds: ['adr-006', 'git-kafka'],
  },
  {
    id: 'retry', label: '重试与死信', subtitle: 'NOTE', type: 'note',
    x: 835, y: 355, size: 52, confidence: 0.84, validFrom: '2025-02', project: '消息中心',
    description: '失败消息经过指数退避重试后进入死信队列，等待人工检查或补偿。',
    evidenceIds: ['adr-006'],
  },
  {
    id: 'eventual', label: '最终一致性', subtitle: 'DECISION', type: 'decision',
    x: 730, y: 510, size: 68, confidence: 0.89, validFrom: '2025-02', project: '订单状态机',
    description: '跨服务流程接受短暂状态差异，通过事件与补偿机制收敛到一致结果。',
    evidenceIds: ['adr-006', 'git-kafka'],
  },
  {
    id: 'dedupe', label: '去重表实现', subtitle: 'SOLUTION', type: 'code',
    x: 840, y: 625, size: 62, confidence: 0.93, validFrom: '2025-06', project: '消息中心',
    description: '使用事件唯一键和数据库约束拦截重复消费，处理完成后记录消费结果。',
    evidenceIds: ['git-kafka'],
  },
  {
    id: 'outbox', label: 'Outbox Pattern', subtitle: 'PATTERN', type: 'pattern',
    x: 300, y: 520, size: 55, confidence: 0.87, validFrom: '2024-08', project: '订单状态机',
    description: '在同一事务中写入业务数据与待发布事件，再由独立任务投递消息。',
    evidenceIds: ['event-note', 'adr-006'],
  },
  {
    id: 'boundary', label: '一致性边界', subtitle: 'OPEN QUESTION', type: 'question',
    x: 405, y: 650, size: 64, confidence: 0.73, validFrom: '2025-06', project: '订单状态机',
    description: '聚合边界是否过大仍待验证，目前需要结合并发冲突和补偿复杂度继续评估。',
    evidenceIds: ['event-note'],
  },
  {
    id: 'review', label: '支付重构复盘', subtitle: 'NOTE', type: 'note',
    x: 160, y: 400, size: 55, confidence: 0.82, validFrom: '2025-02', project: '支付服务',
    description: '记录支付链路重构中的约束、候选方案和上线后的观察结果。',
    evidenceIds: ['event-note'],
  },
]

export const edges: KnowledgeEdge[] = [
  { id: 'e1', source: 'order-state', target: 'event-driven', label: 'implements', highlighted: true },
  { id: 'e2', source: 'outbox', target: 'event-driven', label: 'explained_by', highlighted: true },
  { id: 'e3', source: 'event-driven', target: 'kafka', label: 'depends_on' },
  { id: 'e4', source: 'domain-event', target: 'kafka', label: 'published_to' },
  { id: 'e5', source: 'spring-tx', target: 'kafka', label: 'coordinates' },
  { id: 'e6', source: 'kafka', target: 'retry', label: 'handles_failure_with' },
  { id: 'e7', source: 'event-driven', target: 'eventual', label: 'enables' },
  { id: 'e8', source: 'eventual', target: 'dedupe', label: 'implemented_by' },
  { id: 'e9', source: 'outbox', target: 'boundary', label: 'raises' },
  { id: 'e10', source: 'review', target: 'order-state', label: 'learned_from' },
  { id: 'e11', source: 'review', target: 'outbox', label: 'documents' },
]

export const evidences: Evidence[] = [
  { id: 'event-note', kind: 'md', title: '支付重构复盘.md', location: 'docs/retrospectives', updatedAt: '2 天前', excerpt: '订单状态变化必须与领域事件记录处于同一事务边界，消息发布允许异步完成。' },
  { id: 'domain-event', kind: 'java', title: 'DomainEvent.java', location: 'commerce-core/domain', updatedAt: '4 天前', excerpt: '领域事件携带 aggregateId、occurredAt 和 eventId，消费者以 eventId 保证幂等。' },
  { id: 'adr-006', kind: 'adr', title: 'ADR-006 消息一致性', location: 'docs/architecture', updatedAt: '8 天前', excerpt: '采用 Outbox 与最终一致性，放弃分布式事务；失败消息通过重试和死信队列治理。' },
  { id: 'git-kafka', kind: 'git', title: 'fix: 消费去重与重试', location: 'commit 7fa20bd', updatedAt: '12 天前', excerpt: '新增 consume_record 唯一约束，并将第三次失败后的消息转入 dead-letter topic。' },
]

export const timelinePoints: TimelinePoint[] = [
  { value: 0, date: '2024-05', label: '项目建立' },
  { value: 1, date: '2024-08', label: '引入事件' },
  { value: 2, date: '2025-02', label: '架构演进' },
  { value: 3, date: '2025-06', label: '当前状态' },
]
