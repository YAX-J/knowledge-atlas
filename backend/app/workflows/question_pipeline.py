from langgraph.graph import END, START, StateGraph
from app.workflows.state import WorkflowState
from app.agents.graph_runtime import invoke


def run(code,answer):
    builder=StateGraph(WorkflowState)
    builder.add_node('code_analysis',lambda state:{'code_analysis':code()})
    builder.add_node('evidence_qa',lambda state:{'answer':answer(state.get('code_analysis')),'status':'succeeded'})
    builder.add_edge(START,'code_analysis');builder.add_edge('code_analysis','evidence_qa');builder.add_edge('evidence_qa',END)
    return invoke(builder,{})
