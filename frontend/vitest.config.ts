import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.ts'],
    restoreMocks: true,
    coverage: {
      provider: 'v8',
      include: ['src/App.vue', 'src/api/{client,knowledgeAtlas}.ts', 'src/components/{SourceWorkspace,QuestionWorkspace,KnowledgeSearch,CandidateReview,ProjectGraph,KnowledgeEvolution}.vue',
        'src/pages/AgentWorkspace.vue','src/components/AnswerClaims.vue','src/components/agent/*.vue','src/api/{agents,assistant}.ts','src/composables/{useAgentRuns,useCodeContextSelection,useProjectAssistant}.ts',
        'src/components/{KnowledgeRetirement,KnowledgeManagement,ConversationsWorkspace,Workbench}.vue', 'src/api/workspace.ts',
        'src/composables/{useKnowledgeSearch,useCandidateReview,useProjectGraph,useSourceImport,useKnowledgeRetirement,useConversations,useKnowledgeManagement,useWorkspaceRoute,useEvidenceNavigation,useRepositorySnapshots,useKnowledgeEvolution}.ts'],
      reporter: ['text', 'json-summary', 'lcov'],
      reportsDirectory: '../output/frontend-coverage',
      thresholds: { statements: 55, branches: 50, functions: 35, lines: 60,
        'src/components/ConversationsWorkspace.vue': { lines: 80 },
        'src/composables/useConversations.ts': { lines: 90, branches: 80 } },
    },
  },
})
