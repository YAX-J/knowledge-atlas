from pathlib import Path
import json
from sqlalchemy import create_engine
from app.core.config import Settings
from app.db.base import Base
from app import models
from scripts.evaluate_dataset import validate_dataset
from scripts.prepare_evaluation import load_fixture, prepare_project
from scripts.run_public_acceptance import paired
import uuid

ROOT=Path(__file__).resolve().parents[2]/'evaluation/public-v2'


def test_new_public_pack_is_separate_frozen_and_prepares_through_normal_review():
    manifest,cases,summary=validate_dataset(ROOT)
    protocol=json.loads((ROOT/'protocol.json').read_text(encoding='utf-8'))
    assert summary==protocol['dataset'] and summary['case_count']==20 and summary['source_count']==10
    assert summary['fingerprint_sha256']!=validate_dataset(ROOT.parent)[2]['fingerprint_sha256']
    assert protocol['human_coverage']==0 and not protocol['ranking_tuned_on_this_set']
    engine=create_engine('sqlite+pysqlite://')
    Base.metadata.create_all(engine)
    try:
        prepared=prepare_project(engine=engine,dataset_root=ROOT,project_id=uuid.uuid4(),settings=Settings(_env_file=None),accept_curated_fixture=True)
        assert prepared['counts']['sources']==10 and prepared['counts']['entities']==19
        assert prepared['counts']['reviews']==prepared['counts']['candidates']
    finally:
        engine.dispose()


def test_paired_interval_does_not_invent_human_grades():
    _,cases,_=validate_dataset(ROOT)
    perfect=[dict(id=item['id'],retrieved_evidence=item['gold_evidence']) for item in cases]
    empty=[dict(id=item['id'],retrieved_evidence=[]) for item in cases]
    result=paired({'vector':perfect,'bm25':empty},cases)
    assert result['bm25_minus_vector']['mean']==-1
    assert result['bm25_minus_vector']['ci95']==[-1,-1]


def test_provider_ledger_counts_unknown_attempts_and_fails_closed(tmp_path):
    import pytest
    from scripts.provider_ledger import ProviderLedger
    path=tmp_path/'budget.json'
    ledger=ProviderLedger(path)
    ledger.reserve('answer')
    ledger.reserve('embedding')
    data=json.loads(path.read_text())
    assert data['reserved']=={'model':1,'embedding':1}
    data['reserved']['model']=120
    path.write_text(json.dumps(data))
    with pytest.raises(RuntimeError,match='exhausted'):
        ledger.reserve('answer')
    assert not ledger.lock.exists()


def test_human_review_rejects_blank_duplicate_and_fabricated_grades(tmp_path):
    import csv
    import pytest
    from scripts.review_public import import_grades
    acceptance=ROOT.parent/'results/2026-10-26-public-v2-run1'
    source=acceptance/'blind-review.csv'
    with pytest.raises(ValueError,match='incomplete'):
        import_grades(ROOT,acceptance,source,tmp_path/'complete')
    report=import_grades(ROOT,acceptance,source,tmp_path/'partial',allow_partial=True)
    assert report['scored_rows']==0 and report['coverage']==0 and not report['human_reviewers']
    with source.open(encoding='utf-8-sig',newline='') as file:
        rows=list(csv.DictReader(file)); columns=list(rows[0])
    rows[0].update(answer_correct='true',explainability_score='5',reviewer='')
    invalid=tmp_path/'invalid.csv'
    with invalid.open('w',encoding='utf-8',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=columns);writer.writeheader();writer.writerows(rows)
    with pytest.raises(ValueError,match='real reviewer'):
        import_grades(ROOT,acceptance,invalid,tmp_path/'invalid-results',allow_partial=True)
    rows[-1]=rows[0]
    with invalid.open('w',encoding='utf-8',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=columns);writer.writeheader();writer.writerows(rows)
    with pytest.raises(ValueError,match='without duplicates'):
        import_grades(ROOT,acceptance,invalid,tmp_path/'duplicate-results')
