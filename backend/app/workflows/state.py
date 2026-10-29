from typing import TypedDict


class WorkflowState(TypedDict,total=False):
    code_analysis: dict|None
    extraction_task_id: str
    candidate_ids: list[str]
    answer: dict
    status: str
