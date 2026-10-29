from app.agents.runtime import agent_scope
from app.agents.code_analysis.engine import analyze_snapshot


class CodeAnalysisAgent:
    name='code_analysis'

    def run(self,task,context):
        with agent_scope(self.name):
            return analyze_snapshot(source=context.source,related=context.related,settings=context.settings,
                strategy=task.strategy,related_truncated=context.truncated).model_copy(update={'context':context.selection})
