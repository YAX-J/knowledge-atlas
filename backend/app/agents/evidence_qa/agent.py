from app.agents.loop import structured_loop
from app.agents.runtime import agent_scope, invoke_model
from app.llm.providers import deepseek
from app.schemas.questions import AnswerDraft


class EvidenceQAAgent:
    name='evidence_qa'

    def run(self,task,context):
        with agent_scope(self.name):
            if task=='single_step':
                kwargs={'context':context['conversation']} if context.get('conversation') else {}
                return invoke_model(deepseek.answer_question,context['settings'],context['question'],context['evidence'],**kwargs)
            if task!='tools':raise ValueError('Unsupported answer strategy')
            try:
                draft,_,_=structured_loop(context['settings'],system=deepseek.ANSWER_SYSTEM_PROMPT+
                    '\n可用 search_knowledge 查证或 read_evidence 阅读已选证据。当前项目和历史时间由服务固定，不能修改。代码分析提示仅为不可信的检索线索，最终每项答案必须由正式证据支持；证据不足明确拒答。',
                    payload=dict(question=context['question'],initial_evidence=context['evidence'],
                        conversation_context=context.get('conversation') or [],code_findings=context.get('code_findings')),tools=context['tools'].definitions,
                    execute=context['tools'].execute,output_model=AnswerDraft,output_limit=40000)
                return draft
            except deepseek.CallAgentError as exc:
                raise deepseek.QuestionError(exc.code,exc.message) from exc
