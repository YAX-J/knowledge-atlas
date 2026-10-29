import json
from pathlib import Path
import uuid
from sqlalchemy import create_engine
from app.db.base import Base
from app.core.config import Settings
from scripts.evaluate_dataset import validate_dataset
from scripts.prepare_evaluation import prepare_project

ROOT=Path(__file__).resolve().parents[2]/'evaluation/holdout-v3'


def test_new_upstream_notes_are_frozen_separate_and_replay_temporal_review():
    _,cases,summary=validate_dataset(ROOT)
    protocol=json.loads((ROOT/'protocol.json').read_text(encoding='utf-8'))
    assert protocol['dataset']==summary and summary['case_count']==24 and summary['source_count']==7
    assert summary['category_counts']==dict(cross_document=8,direct_fact=8,temporal=4,unanswerable=4)
    assert protocol['human_coverage']==protocol['provider_calls']==0 and not protocol['ranking_tuned_on_this_set']
    old_questions={item['question'] for item in validate_dataset(ROOT.parent/'public-v2')[1]}
    assert not old_questions & {item['question'] for item in cases}
    engine=create_engine('sqlite+pysqlite://');Base.metadata.create_all(engine)
    try:
        result=prepare_project(engine=engine,dataset_root=ROOT,project_id=uuid.uuid4(),settings=Settings(_env_file=None),accept_curated_fixture=True)
        assert result['counts']['sources']==7 and result['counts']['entities']==19
    finally:engine.dispose()
