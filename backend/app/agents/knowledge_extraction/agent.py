from app.agents.loop import structured_loop
from app.agents.runtime import agent_scope, invoke_model
from app.llm.providers import deepseek
from app.schemas.knowledge import ExtractionDraft
from app.tools.chunks import CHUNK_TOOLS, ChunkTools


class KnowledgeExtractionAgent:
    name='knowledge_extraction'

    def run(self,task,context):
        with agent_scope(self.name):
            if task=='single_step':return invoke_model(deepseek.extract_candidates,context['settings'],context['chunks'])
            if task!='tools':raise ValueError('Unsupported extraction strategy')
            chunks=context['chunks'];tools=ChunkTools(chunks)
            try:
                draft,_,_=structured_loop(context['settings'],system=deepseek.SYSTEM_PROMPT+
                    '\n先调用 read_chunk 核对已列出的原文。仅引用工具读到的精确 quote 和 chunk_id。代码分析提示为派生参考，不是原文证据。最终返回抽取 JSON，不能审核或入图。',
                    payload=dict(chunks=[dict(chunk_id=item['chunk_id'],characters=len(item['content'])) for item in chunks],
                        code_findings=context.get('code_findings',{})),
                    tools=CHUNK_TOOLS,execute=tools.execute,output_model=ExtractionDraft)
                return draft
            except deepseek.CallAgentError as exc:
                raise deepseek.ExtractionError(exc.code,exc.message) from exc
