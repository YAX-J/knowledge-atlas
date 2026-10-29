"""Evidence tools receive scoped callbacks and a bounded server-owned evidence pool."""
import uuid
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.core.errors import AppError


class SearchInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    query: str=Field(min_length=1,max_length=200)
    mode: Literal['bm25','bm25_source','rrf','hybrid','vector']='bm25'


class EvidenceInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    evidence_id: uuid.UUID


def payload(item):
    return dict(id=str(item.id),entity_name=item.entity_name,title=item.title,start_line=item.start_line,
        end_line=item.end_line,quote=item.quote,entity_names=[entity.name for entity in item.related_entities])


class EvidenceTools:
    definitions=[dict(type='function',function=dict(name=name,description=description,parameters=schema.model_json_schema()))
        for name,description,schema in [('search_knowledge','Search confirmed knowledge in the fixed project/time. Scores are not answerability.',SearchInput),
        ('read_evidence','Read one evidence item already returned in this run. No arbitrary source IDs.',EvidenceInput)]]

    def __init__(self,search,evidence):
        self.search=search;self.evidence=evidence

    def execute(self,name,arguments):
        try:
            if not isinstance(arguments,str) or len(arguments)>4000:raise ValueError()
            if name=='search_knowledge':
                args=SearchInput.model_validate_json(arguments)
                if not args.query.strip():raise ValueError()
                records=self.search(args.query.strip(),args.mode)
                for identifier,item in records.items():
                    if len(self.evidence)<12:self.evidence.setdefault(identifier,item)
                return dict(evidence=[payload(item) for identifier,item in records.items() if identifier in self.evidence],
                    truncated=any(identifier not in self.evidence for identifier in records))
            if name=='read_evidence':
                args=EvidenceInput.model_validate_json(arguments);item=self.evidence.get(args.evidence_id)
                return payload(item) if item else {'error':'EVIDENCE_OUT_OF_SCOPE'}
            return {'error':'TOOL_NOT_ALLOWED'}
        except (ValueError,TypeError):return {'error':'INVALID_ARGUMENTS'}
        except AppError as exc:
            if exc.code=='AGENT_BUDGET_EXCEEDED':raise
            return {'error':exc.code}
