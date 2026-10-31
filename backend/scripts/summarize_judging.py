"""Offline model-judgment summaries with full-case and graded-subset denominators.

No provider calls, inferred human grades, threshold changes or input mutations.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from scripts.evaluate_dataset import read_jsonl, validate_dataset
from scripts.jev_evaluation import digest, requests, verified_passage


def aggregate(rows):
    graded=[row for row in rows if row['quality'] is not None]
    counts={name:dict(Counter(row['quality'][name]['choice'] for row in graded))
            for name in ('correctness','completeness','abstention')}
    low={name:sum(row['quality'][name]['confidence'] is None or row['quality'][name]['confidence']<.8 for row in graded)
         for name in counts}
    units=[unit for row in rows for unit in row['citation_units']]
    judged=[unit for unit in units if unit['judged']]
    correct=counts['correctness'].get('correct',0)
    return dict(total_cases=len(rows),invalid_outputs=sum(row['invalid_output'] for row in rows),
        valid_exports=sum(not row['invalid_output'] for row in rows),quality_graded=len(graded),
        raw_quality_labels=counts,quality_low_confidence=low,
        model_correct_label_fraction_all=correct/len(rows) if rows else None,
        model_correct_label_fraction_graded=correct/len(graded) if graded else None,
        citation_units=len(units),citation_units_judged=len(judged),
        citation_uncertain=sum(unit['uncertain'] for unit in judged),
        citation_order_disagreement=sum(unit['order_disagreement'] for unit in judged),
        high_confidence_double_order_supported=sum(unit['stable_supported'] for unit in judged),
        stable_supported_fraction_all_cited_units=sum(unit['stable_supported'] for unit in judged)/len(units) if units else None,
        valid_answers_without_cited_units=sum(not row['invalid_output'] and not row['citation_units'] for row in rows),
        human_grading_coverage=0)


def summarize(dataset,answers_dir,packet_dir,source_run,output,*,allow_partial=False):
    dataset,answers_dir,packet_dir,source_run,output=map(Path,(dataset,answers_dir,packet_dir,source_run,output))
    if output.exists():raise ValueError('Output directory must be new')
    _,cases,summary=validate_dataset(dataset)
    cases={case['id']:case for case in cases}
    files=[dataset/'manifest.json',dataset/'cases.jsonl',source_run]
    def read(path):
        files.append(path)
        return json.loads(path.read_text(encoding='utf-8'))
    packet=read(packet_dir/'packet.json')
    manifest=read(packet_dir/'packet-manifest.json')
    key=read(packet_dir/'grading-key.json')
    excluded=read(packet_dir/'excluded-answers.json') if 'excluded_answers_sha256' in manifest else []
    run=json.loads(source_run.read_text(encoding='utf-8'))
    if (manifest['dataset']!=summary or digest(packet)!=manifest['packet_sha256']
            or run['packet_sha256']!=manifest['packet_sha256']
            or run['judge_config_sha256']!=digest(run['judge_config'])
            or run['human_grading_coverage']!=0):
        raise ValueError('Dataset, packet, run or judge configuration fingerprint mismatch')
    if 'excluded_answers_sha256' in manifest and digest(excluded)!=manifest['excluded_answers_sha256']:
        raise ValueError('Exclusion fingerprint mismatch')
    if run['status']!='succeeded' and not (allow_partial and run['status']=='failed'):
        raise ValueError('A completed run is required; partial reporting must be explicit')
    reviews={row['review_id']:row for row in packet}
    if len(reviews)!=len(packet) or set(key)!=set(reviews):raise ValueError('Invalid grading-key coverage')
    jobs={(row['review_id'],name):questions for row in packet for name,_state,questions in requests(row)}
    results={}
    for result in run['results']:
        identifier=(result['review_id'],result['part'])
        if identifier not in jobs or identifier in results:raise ValueError('Unknown or duplicate judge result')
        questions=jobs[identifier]
        if set(result['answers'])!=set(questions) or any(result['answers'][name]['choice'] not in question['criteria']
                for name,question in questions.items()):raise ValueError('Invalid judge labels')
        results[identifier]=result
    if (run['completed_requests']!=len(results) or run['reserved_requests']<len(results)
            or run['reserved_requests']>run['max_requests'] or run['planned_requests']!=len(jobs)):
        raise ValueError('Inconsistent request counters')
    if run['status']=='succeeded' and (set(results)!=set(jobs) or run['model_graded_reviews']!=len(packet)):
        raise ValueError('Completed run is missing judge jobs')
    by_pair={}
    for identifier,link in key.items():
        pair=(link['prediction'],link['case_id'])
        if pair in by_pair:raise ValueError('Duplicate method/case mapping')
        by_pair[pair]=identifier
    excluded_pairs={(item['prediction'],item['case_id']) for item in excluded}
    if len(excluded_pairs)!=len(excluded) or excluded_pairs & set(by_pair):raise ValueError('Overlapping/duplicate exclusions')
    names=sorted({name for name,_ in set(by_pair)|excluded_pairs})
    rows=[]
    for name in names:
        if Path(name).name!=name or not name.endswith('.jsonl'):raise ValueError('Prediction path must be a filename')
        file=answers_dir/name;files.append(file)
        predictions=read_jsonl(file)
        if len(predictions)!=len(cases) or {row['id'] for row in predictions}!=set(cases):
            raise ValueError('Every method must export every case exactly once')
        for prediction in predictions:
            case=cases[prediction['id']];pair=(name,case['id'])
            row=dict(method=Path(name).stem,case_id=case['id'],category=case['category'],answerable=case['answerable'],
                     invalid_output=pair in excluded_pairs,review_id=by_pair.get(pair),quality=None,citation_units=[],human_grade=None)
            if row['invalid_output']:
                if (prediction.get('failure',{}).get('code')!='QUESTION_OUTPUT_INVALID'
                        or prediction.get('answer') is not None or prediction.get('supported') is not None):
                    raise ValueError('Exclusion is not a recorded invalid output')
            else:
                if pair not in by_pair:raise ValueError('Missing method/case coverage')
                identifier=by_pair[pair];review=reviews[identifier]
                if (review['answer']!=prediction['answer'] or review['question']!=case['question']
                        or review['reference_answer']!=case['gold_answer'] or review['required_facts']!=case['required_facts']
                        or review['answerable']!=case['answerable'] or review['supported']!=prediction['supported']):
                    raise ValueError('Anonymous answer/reference does not match source export')
                if prediction.get('claims') is not None:
                    evidence={item['id']:verified_passage(dataset,item) for item in prediction['claim_evidence']}
                    units=[dict(claim=claim['text'],passages=[evidence[identifier] for identifier in claim['citation_ids']])
                           for claim in prediction['claims'] if claim['status']=='supported']
                else:
                    citations=[verified_passage(dataset,item) for item in prediction['citations']]
                    units=[dict(claim=prediction['answer'],passages=citations)] if citations else []
                if review['units']!=units:raise ValueError('Anonymous support units do not match source citations')
                quality=results.get((identifier,'quality'))
                row.update(granularity=review['granularity'],quality=quality['answers'] if quality else None)
                uncertain=[]
                for index in range(len(units)):
                    a=results.get((identifier,f'support-{index}-forward'))
                    b=results.get((identifier,f'support-{index}-reversed'))
                    a=a['answers']['relation'] if a else None;b=b['answers']['relation'] if b else None
                    judged=a is not None and b is not None
                    disagreement=judged and a['choice']!=b['choice']
                    low=judged and any(item['confidence'] is None or item['confidence']<.8 for item in (a,b))
                    unit=dict(forward=a,reversed=b,judged=judged,uncertain=bool(disagreement or low),
                              order_disagreement=bool(disagreement),stable_supported=bool(judged and not disagreement and not low and a['choice']=='supported'))
                    row['citation_units'].append(unit)
                    if unit['uncertain']:uncertain.append(index)
                if run['status']=='succeeded':
                    recorded=[item for item in run['reviews'] if item['review_id']==identifier]
                    if len(recorded)!=1 or recorded[0]['uncertain_units']!=uncertain:
                        raise ValueError('Stored uncertainty disagrees with the frozen protocol')
            rows.append(row)
    expected={(name,identifier) for name in names for identifier in cases}
    if set(by_pair)|excluded_pairs!=expected:raise ValueError('Full-case denominator mismatch')
    if 'answer_coverage' in manifest and manifest['answer_coverage']!=dict(exported=len(rows),gradable=len(packet),invalid_output=len(excluded)):
        raise ValueError('Coverage manifest mismatch')
    methods={name:aggregate([row for row in rows if row['method']==name]) for name in sorted({row['method'] for row in rows})}
    categories={method:{category:aggregate([row for row in rows if row['method']==method and row['category']==category])
        for category in sorted({row['category'] for row in rows})} for method in methods}
    usage=[item.get('usage') for item in run['results']]
    numeric_usage=[item for item in usage if item is not None]
    report=dict(protocol='model-judgment-summary-v1',source_status=run['status'],dataset=summary,
        annotation_source='model',human_grading_coverage=0,judge_config=run['judge_config'],
        provider_requests_this_summary=0,source_reserved_requests=run['reserved_requests'],source_completed_requests=run['completed_requests'],
        global_summary=aggregate(rows),methods=methods,categories=categories,
        usage=dict(complete=len(numeric_usage)==len(usage),input_tokens=sum(item['input_tokens'] for item in numeric_usage),
                   output_tokens=sum(item['output_tokens'] for item in numeric_usage),actual_billed_cost=None),
        input_sha256={(path.resolve().relative_to(Path(__file__).resolve().parents[2]).as_posix()
                      if path.resolve().is_relative_to(Path(__file__).resolve().parents[2]) else path.name):
                      hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
        limitations=['Model labels are not human accuracy or calibrated probabilities.',
                    'Correct/all and correct/graded are separate label fractions; invalid outputs remain explicit.',
                    'Quality low-confidence counts are descriptive; raw labels and citation threshold0.8 are unchanged.',
                    'Agent-authored references and unpinned judge weights limit inference.'])
    output.mkdir(parents=True,exist_ok=False)
    (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'per-answer.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('dataset','answers','packet','source-run','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--allow-partial',action='store_true')
    args=parser.parse_args()
    report=summarize(args.dataset,args.answers,args.packet,args.source_run,args.output,allow_partial=args.allow_partial)
    print(json.dumps(dict(source_status=report['source_status'],total_cases=report['global_summary']['total_cases'],
                         graded=report['global_summary']['quality_graded'],new_provider_requests=0)))


if __name__=='__main__':main()
