import json
from pathlib import Path

import pytest

from scripts import summarize_judging as summary_tool
from scripts.jev_evaluation import digest,requests,verified_passage


def write(path,value):
    path.write_text(json.dumps(value),encoding='utf-8')


def fixture(tmp_path,monkeypatch):
    dataset=tmp_path/'dataset';dataset.mkdir();(dataset/'corpus').mkdir()
    (dataset/'corpus/doc.md').write_text('fact\ncontext\n',encoding='utf-8')
    cases=[dict(id='a',category='direct_fact',question='Fact?',answerable=True,gold_answer='fact',required_facts=['fact']),
           dict(id='b',category='unanswerable',question='Unknown?',answerable=False,gold_answer='Unknown',required_facts=[])]
    metadata={'dataset_id':'unit-fixture','fingerprint_sha256':'unit'}
    monkeypatch.setattr(summary_tool,'validate_dataset',lambda _:(None,cases,metadata))
    write(dataset/'manifest.json',metadata);(dataset/'cases.jsonl').write_text('{}\n')
    answers=tmp_path/'answers';answers.mkdir()
    packet_dir=tmp_path/'packet';packet_dir.mkdir()
    evidence=dict(id='evidence',source='corpus/doc.md',start_line=1,end_line=1,quote='fact')
    rows=[];key={};excluded=[]
    for mode in ('bm25','vector'):
        predictions=[]
        for case in cases:
            if mode=='bm25' and case['id']=='b':
                predictions.append(dict(id='b',answer=None,supported=None,failure={'code':'QUESTION_OUTPUT_INVALID'}))
                excluded.append(dict(prediction=mode+'.jsonl',case_id='b',code='QUESTION_OUTPUT_INVALID'))
                continue
            supported=case['answerable'];answer='fact' if supported else 'Unknown'
            claims=[dict(text=answer,status='supported' if supported else 'insufficient',citation_ids=['evidence'] if supported else [])]
            prediction=dict(id=case['id'],answer=answer,supported=supported,claims=claims,claim_evidence=[evidence] if supported else [])
            predictions.append(prediction)
            identifier='review-'+str(len(rows))
            units=[dict(claim='fact',passages=[verified_passage(dataset,evidence)])] if supported else []
            rows.append(dict(review_id=identifier,question=case['question'],answer=answer,supported=supported,
                reference_answer=case['gold_answer'],required_facts=case['required_facts'],answerable=supported,granularity='claim',units=units))
            key[identifier]=dict(prediction=mode+'.jsonl',case_id=case['id'])
        (answers/(mode+'.jsonl')).write_text(''.join(json.dumps(row)+'\n' for row in predictions))
    manifest=dict(dataset=metadata,packet_sha256=digest(rows),excluded_answers_sha256=digest(excluded),answer_coverage=dict(exported=4,gradable=3,invalid_output=1))
    for name,value in [('packet.json',rows),('packet-manifest.json',manifest),('grading-key.json',key),('excluded-answers.json',excluded)]:
        write(packet_dir/name,value)
    results=[];reviews=[]
    for row in rows:
        low=key[row['review_id']]['prediction']=='bm25.jsonl'
        for name,_state,questions in requests(row):
            result={}
            for field,question in questions.items():
                choice='supported' if field=='relation' else {'correctness':'correct','completeness':'complete','abstention':'appropriate'}[field]
                confidence=.7 if low or field=='abstention' else .9
                result[field]=dict(choice=choice,confidence=confidence,probabilities={option:float(option==choice) for option in question['criteria']})
            results.append(dict(review_id=row['review_id'],part=name,answers=result,usage=dict(input_tokens=10,output_tokens=0)))
        reviews.append(dict(review_id=row['review_id'],uncertain_units=[0] if low and row['units'] else []))
    run=dict(status='succeeded',packet_sha256=manifest['packet_sha256'],judge_config={'model':'test-clef'},
             judge_config_sha256=digest({'model':'test-clef'}),human_grading_coverage=0,results=results,reviews=reviews,
             completed_requests=len(results),reserved_requests=len(results),max_requests=len(results),planned_requests=len(results),model_graded_reviews=len(rows))
    source=tmp_path/'run.json';write(source,run)
    return dataset,answers,packet_dir,source,rows,run


def test_summary_keeps_failed_cases_denominators_confidence_and_human_zero(tmp_path,monkeypatch):
    dataset,answers,packet_dir,source,_rows,_run=fixture(tmp_path,monkeypatch)
    before={path:path.read_bytes() for path in tmp_path.rglob('*') if path.is_file()}
    result=summary_tool.summarize(dataset,answers,packet_dir,source,tmp_path/'summary')
    bm25=result['methods']['bm25'];vector=result['methods']['vector']
    assert bm25['total_cases']==2 and bm25['invalid_outputs']==1 and bm25['quality_graded']==1
    assert bm25['model_correct_label_fraction_all']==.5 and bm25['model_correct_label_fraction_graded']==1
    assert bm25['citation_uncertain']==1 and bm25['high_confidence_double_order_supported']==0
    assert vector['high_confidence_double_order_supported']==1
    assert result['global_summary']['quality_graded']==3 and result['global_summary']['total_cases']==4
    assert result['usage']['input_tokens']==70 and result['usage']['actual_billed_cost'] is None
    assert result['provider_requests_this_summary']==result['human_grading_coverage']==0
    assert all(path.read_bytes()==value for path,value in before.items())
    rows=[json.loads(line) for line in (tmp_path/'summary/per-answer.jsonl').read_text().splitlines()]
    invalid=next(row for row in rows if row['invalid_output'])
    assert invalid['quality'] is invalid['human_grade'] is None
    assert result['categories']['bm25']['unanswerable']['total_cases']==1


@pytest.mark.parametrize('mutation',['packet','config','duplicate','answer','mapping','exclusion','overwrite'])
def test_summary_refuses_changed_or_inconsistent_inputs(tmp_path,monkeypatch,mutation):
    dataset,answers,packet_dir,source,rows,run=fixture(tmp_path,monkeypatch)
    target=tmp_path/'summary'
    if mutation=='packet': rows[0]['answer']='changed';write(packet_dir/'packet.json',rows)
    if mutation=='config':run['judge_config']['model']='changed';write(source,run)
    if mutation=='duplicate':run['results'].append(run['results'][0]);write(source,run)
    if mutation=='answer':
        values=[json.loads(line) for line in (answers/'bm25.jsonl').read_text().splitlines()]
        values[0]['answer']='changed';(answers/'bm25.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in values))
    if mutation=='mapping':
        key=json.loads((packet_dir/'grading-key.json').read_text());key['review-0']['prediction']='vector.jsonl';write(packet_dir/'grading-key.json',key)
    if mutation=='exclusion':write(packet_dir/'excluded-answers.json',[])
    if mutation=='overwrite':target.mkdir()
    with pytest.raises(ValueError):summary_tool.summarize(dataset,answers,packet_dir,source,target)


def test_explicit_partial_summary_does_not_invent_missing_support_or_quality(tmp_path,monkeypatch):
    dataset,answers,packet_dir,source,_rows,run=fixture(tmp_path,monkeypatch)
    run.update(status='failed',results=run['results'][:2],completed_requests=2,reserved_requests=3,model_graded_reviews=0)
    write(source,run)
    with pytest.raises(ValueError,match='partial reporting'):
        summary_tool.summarize(dataset,answers,packet_dir,source,tmp_path/'strict')
    result=summary_tool.summarize(dataset,answers,packet_dir,source,tmp_path/'partial',allow_partial=True)
    assert result['global_summary']['quality_graded']==1
    assert result['global_summary']['citation_units_judged']==0
    assert result['global_summary']['citation_units']==2
