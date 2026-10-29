from langgraph.graph import END, START, StateGraph
from app.workflows.state import WorkflowState
from app.agents.graph_runtime import invoke


def run(code,extract):
    def analyze(state):return {'code_analysis':code()}
    def propose(state):return extract(state.get('code_analysis'))
    builder=StateGraph(WorkflowState)
    builder.add_node('code_analysis',analyze);builder.add_node('knowledge_extraction',propose)
    builder.add_edge(START,'code_analysis');builder.add_edge('code_analysis','knowledge_extraction')
    builder.add_edge('knowledge_extraction',END)
    return invoke(builder,{})
