"""A bounded LangGraph model/tool loop, with no automatic provider retry or tracing upload."""
import json
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from app.agents.runtime import invoke_model, invoke_tool
from app.agents.graph_runtime import invoke
from app.llm.providers import deepseek


class LoopState(TypedDict, total=False):
    messages: list[dict]
    turn: int
    trace: list[dict]
    used_ids: set[str]
    total_input: int
    total_output: int
    draft: object
    calls: list[dict]


def structured_loop(settings, *, system, payload, tools, execute, output_model,
                    max_turns=4, max_tools=8, output_limit=20000, input_limit=240000, seconds=230):
    deadline=time.monotonic()+seconds
    allowed={item['function']['name'] for item in tools}

    def fail(code='CALL_AGENT_BUDGET_EXCEEDED',message='Agent 工具、输入或时间达到上限，请缩小范围'):
        raise deepseek.CallAgentError(code,message)

    def model_node(state: LoopState):
        serialized=json.dumps(state['messages'],ensure_ascii=False)
        total=state['total_input']+len(serialized)
        remaining=deadline-time.monotonic()
        if len(serialized)>settings.extraction_max_input_chars or total>input_limit or remaining<5:fail()
        configuration=settings.model_copy(update={'deepseek_timeout_seconds':min(settings.deepseek_timeout_seconds,remaining)})
        message=invoke_model(deepseek.call_agent_turn,configuration,state['messages'],tools,
            finish=state['turn']==max_turns-1,require_tool=state['turn']==0)
        calls=message.get('tool_calls',[])
        if not calls:
            try:draft=output_model.model_validate_json(message['content'])
            except (KeyError,ValueError,TypeError,ValidationError):
                fail('CALL_AGENT_OUTPUT_INVALID','Agent 未返回符合约定的结构化结果')
            return dict(draft=draft,turn=state['turn']+1,total_input=total,calls=[])
        if not isinstance(calls,list) or state['turn']==max_turns-1 or len(calls)+len(state['trace'])>max_tools:fail()
        used=set(state['used_ids']);normalized=[]
        for call in calls:
            if not isinstance(call,dict) or call.get('type')!='function' or not isinstance(call.get('function'),dict):
                fail('CALL_AGENT_OUTPUT_INVALID','Agent 工具调用格式无效')
            identifier=call.get('id');function=call['function']
            if not isinstance(identifier,str) or not 1<=len(identifier)<=128 or identifier in used or not isinstance(function.get('name'),str):
                fail('CALL_AGENT_OUTPUT_INVALID','Agent 工具标识无效')
            used.add(identifier);normalized.append(dict(id=identifier,type='function',function=function))
        return dict(turn=state['turn']+1,total_input=total,calls=normalized,used_ids=used,
            messages=[*state['messages'],dict(role='assistant',content=None,tool_calls=normalized)])

    def tool_node(state: LoopState):
        messages=list(state['messages']);trace=list(state['trace']);total=state['total_output']
        for call in state['calls']:
            function=call['function'];name=function['name'];started=time.monotonic()
            result=invoke_tool(execute,name,function.get('arguments'))
            content=json.dumps(result,ensure_ascii=False);total+=len(content)
            if total>output_limit:fail()
            trace.append(dict(name=name if name in allowed else 'not_allowed',status='error' if 'error' in result else 'ok',
                result_characters=len(content),duration_ms=round((time.monotonic()-started)*1000,3)))
            messages.append(dict(role='tool',tool_call_id=call['id'],content=content))
        return dict(messages=messages,trace=trace,total_output=total)

    builder=StateGraph(LoopState)
    builder.add_node('model',model_node);builder.add_node('tools',tool_node)
    builder.add_edge(START,'model')
    builder.add_conditional_edges('model',lambda state: 'tools' if state['calls'] else END)
    builder.add_edge('tools','model')
    result=invoke(builder,dict(messages=[dict(role='system',content=system),
        dict(role='user',content=json.dumps(payload,ensure_ascii=False))],turn=0,trace=[],used_ids=set(),total_input=0,total_output=0),
        recursion_limit=2*max_turns+2)
    return result['draft'],result['turn'],result['trace']
