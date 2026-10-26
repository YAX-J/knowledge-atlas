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
      include: ['src/api/client.ts', 'src/components/{SourceWorkspace,QuestionWorkspace,KnowledgeSearch,CandidateReview}.vue',
        'src/components/{KnowledgeRetirement,KnowledgeManagement,ConversationsWorkspace,Workbench}.vue', 'src/api/workspace.ts',
        'src/composables/{useKnowledgeSearch,useCandidateReview,useProjectGraph,useSourceImport,useKnowledgeRetirement,useConversations,useKnowledgeManagement}.ts'],
      reporter: ['text', 'json-summary', 'lcov'],
      reportsDirectory: '../output/frontend-coverage',
      thresholds: { statements: 45, branches: 40, functions: 25, lines: 45 },
    },
  },
})
