"""Per-run scope, atomic budgets and content-free events, shared across agents."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import RLock
from typing import Callable
import time
import uuid

from app.core.errors import AppError

_current: ContextVar['RunContext | None'] = ContextVar('agent_run', default=None)
_agent: ContextVar[str] = ContextVar('agent_name', default='workflow')


class AgentPaused(Exception):
    """A durable human checkpoint, distinct from an execution failure."""


@dataclass
class RunContext:
    user_id: uuid.UUID
    project_id: uuid.UUID
    run_id: uuid.UUID = field(default_factory=uuid.uuid4)
    source_id: uuid.UUID | None = None
    snapshot_id: uuid.UUID | None = None
    valid_at: str | None = None
    model_limit: int = 8
    tool_limit: int = 16
    embedding_limit: int = 4
    seconds: float = 900
    events: list[dict] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: {'model':0,'tool':0,'embedding':0})
    agent_counts: dict[str, int] = field(default_factory=dict)
    role_limits: dict[str,dict[str,int]] = field(default_factory=dict)
    started: float = field(default_factory=time.monotonic)
    on_progress: Callable[['RunContext'], None] | None = field(default=None, repr=False, compare=False)
    _progress_failed: bool = field(default=False, init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def event(self, kind, status='ok', **numbers):
        # Event vocabulary is supplied by code, never by provider arguments/text.
        with self._lock:
            if len(self.events) >= 256:
                raise AppError(status_code=429, code='AGENT_BUDGET_EXCEEDED', message='Agent 事件预算已用尽')
            self.events.append(dict(sequence=len(self.events)+1, agent=_agent.get(), kind=kind,
                status=status, elapsed_ms=round((time.monotonic()-self.started)*1000,3), **numbers))
            if self.on_progress is not None:
                try:
                    self.on_progress(self)
                except Exception as exc:
                    # Never issue another external call after losing durable progress.
                    self._progress_failed = True
                    self.on_progress = None
                    if isinstance(exc, AppError):
                        raise
                    raise AppError(status_code=503, code='WORKFLOW_PROGRESS_UNAVAILABLE',
                        message='任务进度暂时无法保存，已停止后续调用，请读取任务状态') from None

    def reserve(self, kind):
        with self._lock:
            if self._progress_failed:
                raise AppError(status_code=503, code='WORKFLOW_PROGRESS_UNAVAILABLE',
                    message='任务进度暂时无法保存，已停止后续调用，请读取任务状态')
            agent=_agent.get(); key=agent+':'+kind
            maximum={'model':self.model_limit,'tool':self.tool_limit,'embedding':self.embedding_limit}[kind]
            own_maximum={'model':4,'tool':8,'embedding':4}[kind]
            own_maximum=self.role_limits.get(agent,{}).get(kind,own_maximum)
            if time.monotonic()-self.started > self.seconds or self.counts[kind]>=maximum or self.agent_counts.get(key,0)>=own_maximum:
                raise AppError(status_code=429, code='AGENT_BUDGET_EXCEEDED', message='本次任务的 Agent 调用或时间预算已用尽')
            self.counts[kind]+=1;self.agent_counts[key]=self.agent_counts.get(key,0)+1
            self.event(kind,'started',attempt=self.counts[kind])

    def usage(self):
        with self._lock:
            return dict(**self.counts, limits=dict(model=self.model_limit,tool=self.tool_limit,embedding=self.embedding_limit))


@contextmanager
def run_scope(context):
    existing=_current.get()
    if existing is not None and existing is not context:
        raise AppError(status_code=409,code='AGENT_CONTEXT_CONFLICT',message='不允许在同一任务中切换用户或项目上下文')
    token=_current.set(context)
    try: yield context
    finally: _current.reset(token)


@contextmanager
def agent_scope(name):
    token=_agent.set(name)
    context=_current.get()
    try:
        if context:context.event('agent','started')
        yield
        if context:context.event('agent','succeeded')
    except AgentPaused:
        if context:context.event('agent','waiting_approval')
        raise
    except Exception:
        if context:context.event('agent','failed')
        raise
    finally:_agent.reset(token)


def invoke_model(callback, *args, **kwargs):
    context=_current.get()
    if context:context.reserve('model')
    try:
        result=callback(*args,**kwargs)
        if context:context.event('model','succeeded')
        return result
    except Exception:
        if context:context.event('model','failed')
        raise


def invoke_tool(callback, *args, **kwargs):
    context=_current.get()
    if context:context.reserve('tool')
    allowed={'read_source_range','get_imports','search_symbols','find_references','get_type_members','read_chunk','read_evidence','search_knowledge','search_sources','read_source_chunk'}
    allowed|={'get_project_overview','list_project_sources','get_parse_status','search_notes','read_note_revision',
        'inspect_knowledge_conflicts','analyze_code','create_note_draft','propose_note_revision','snapshot_note_revision',
        'import_repository_snapshot','request_source_parse','propose_knowledge','propose_knowledge_change','create_report_draft'}
    tool_name = args[0] if args and args[0] in allowed else 'not_allowed'
    try:
        result=callback(*args,**kwargs)
    except Exception:
        if context:context.event('tool','failed',tool_name=tool_name)
        raise
    if context:context.event('tool','error' if isinstance(result,dict) and 'error' in result else 'succeeded',
        tool_name=tool_name)
    return result


def embedding_attempt():
    context=_current.get()
    if context:context.reserve('embedding')
