import {
  Aim, ChatDotRound, Check, Clock, Collection, Connection, DataAnalysis, Document, Files,
  Fold, Grid, Memo, Search, Setting, Share, Tickets,
} from '@element-plus/icons-vue'

export const deckGroups = [
  { id: 'explore', label: '探索', items: [
    { id: 'graph', label: '知识图谱', caption: '关系与时序回放', icon: Connection },
    { id: 'search', label: '混合检索', caption: '在当前项目中检索', icon: Search },
    { id: 'questions', label: '证据问答', caption: '查找证据并回答', icon: ChatDotRound },
    { id: 'conversations', label: '问答会话', caption: '回看问题、回答与引用', icon: Clock },
  ] },
  { id: 'collect', label: '沉淀', items: [
    { id: 'sources', label: '资料库', caption: '导入、资料与仓库', icon: Document },
    { id: 'notes', label: '项目笔记', caption: '笔记与修订', icon: Memo },
    { id: 'review', label: '候选审核', caption: '核对候选与来源原文', icon: Check },
    { id: 'workbench', label: '工作台', caption: '项目总览与待办', icon: Grid },
  ] },
  { id: 'organize', label: '整理', items: [
    { id: 'govern', label: '知识治理', caption: '演化与治理建议', icon: Aim },
    { id: 'identity', label: '实体消歧', caption: '别名、合并与身份整理', icon: Share },
    { id: 'retirement', label: '停用审计', caption: '纠错与停用记录', icon: Fold },
  ] },
  { id: 'collaborate', label: '协作', items: [
    { id: 'agents', label: 'Agent 协作', caption: '任务、流程与审批', icon: Setting },
  ] },
] as const

export const deckCommands = [
  ...deckGroups.flatMap<typeof deckGroups[number]['items'][number]>(group => group.items),
  { id: 'projects', label: '我的项目', caption: '切换或创建项目', icon: Files },
  { id: 'repositories', label: '来源仓库', caption: '登记来源与查看快照', icon: Collection },
  { id: 'code', label: '代码结构', caption: '在资料库中检索代码符号', icon: Tickets },
  { id: 'demo', label: '独立演示图谱', caption: '浏览示例知识与时间线', icon: DataAnalysis },
]
