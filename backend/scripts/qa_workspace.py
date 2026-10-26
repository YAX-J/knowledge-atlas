"""Disposable native browser workspace with clearly synthetic providers and real API persistence."""
import argparse
from pathlib import Path
import uuid
from unittest.mock import patch
import uvicorn
from pydantic import SecretStr
from sqlalchemy.orm import Session
from app.core import config as configuration
from app.core.identity import DEVELOPMENT_USER_ID as USER
from app.models.domain import Project
from app.schemas.knowledge import ExtractionDraft
from app.schemas.questions import AnswerDraft
from app.services import deepseek,embeddings
from scripts.isolated_workspace import isolated_workspace
from scripts.prepare_evaluation import prepare_project


def extraction(_settings,chunks):
    item=next((item for item in chunks if item['content'].strip() and not item['content'].lstrip().startswith('#')),chunks[0])
    quote=item['content'].strip()[:250]
    evidence=[dict(chunk_id=item['chunk_id'],quote=quote)]
    return ExtractionDraft.model_validate(dict(entities=[
        dict(local_id='index',type='Concept',name='知识索引',summary=quote,confidence=.9,evidence=evidence),
        dict(local_id='strategy',type='Concept',name='索引策略',summary=quote,confidence=.9,evidence=evidence)],
        relations=[dict(local_id='uses',type='USES',source='index',target='strategy',summary=quote,confidence=.9,evidence=evidence)]))


def answer(_settings,question,evidence,**kwargs):
    return AnswerDraft(supported=True,answer='本地验收替身引用当前原文：'+evidence[0]['quote'],confidence=.9,
        citation_ids=[evidence[0]['id']],missing_information=[])


def vectors(_settings,texts):
    result=[]
    for text in texts:
        vector=[0.]*1024
        vector[sum(text.encode())%16]=1.
        result.append(vector)
    return result


def main(port,frontend_origin):
    base=configuration.get_settings()
    with isolated_workspace(base) as (engine,native,schema):
        native=native.model_copy(update=dict(cors_origins=[frontend_origin],deepseek_api_key=SecretStr('qa-only-stub'),
            deepseek_model='qa-local-stub',embedding_api_key=SecretStr('qa-only-stub'),embedding_model='qa-local',embedding_base_url='https://qa.invalid/v1'))
        prepared=prepare_project(engine=engine,dataset_root=Path(__file__).resolve().parents[2]/'evaluation/public-v2',
            project_id=uuid.uuid4(),settings=native,accept_curated_fixture=True)
        with Session(engine) as db:
            project=db.get(Project,uuid.UUID(prepared['project_id']))
            project.name='开发知识整理 · 临时验收'
            project.description='固定提交的公开源码与合成笔记。此工作区使用本地模型替身，仅用于功能验收。'
            db.commit()
        # Import API after selecting the private schema/configuration; override DB explicitly too.
        def no_remote(*_args,**_kwargs):
            raise deepseek.CallAgentError('QA_PROVIDER_DISABLED','本地验收使用模型替身；真实代码 Agent 已在公开源码单独验收。')
        with (patch.object(configuration,'get_settings',lambda:native),patch.object(deepseek,'extract_candidates',extraction),
             patch.object(deepseek,'answer_question',answer),patch.object(embeddings,'embed_texts',vectors),
             patch.object(deepseek,'analyze_cross_file_calls',no_remote),patch.object(deepseek,'call_agent_turn',no_remote)):
            from app.main import app
            from app.db.session import get_db
            def db_session():
                with Session(engine,expire_on_commit=False) as db:
                    yield db
            app.dependency_overrides[get_db]=db_session
            try:
                with Session(engine) as db:
                    embeddings.rebuild_project_embeddings(db,user_id=USER,project_id=uuid.UUID(prepared['project_id']),settings=native)
                print(f'Disposable browser workspace ready on port {port}; providers are local stubs; no application schema writes.',flush=True)
                uvicorn.run(app,host='127.0.0.1',port=port,log_level='warning')
            finally:
                app.dependency_overrides.pop(get_db,None)
    print('Disposable browser schema removed.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8010)
    parser.add_argument('--frontend-origin',default='http://127.0.0.1:5180')
    args=parser.parse_args()
    main(args.port,args.frontend_origin)
