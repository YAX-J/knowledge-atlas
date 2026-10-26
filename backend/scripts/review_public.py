"""Export an offline blind review page or score actual human CSV grades; never infer missing scores."""
import argparse
import csv
import json
from pathlib import Path
from scripts.evaluate_dataset import read_jsonl,score_predictions,validate_dataset


def export_page(dataset,acceptance):
    _,cases,summary=validate_dataset(dataset)
    by_id={item['id']:item for item in cases}
    key=json.loads((acceptance/'grading-key.json').read_text(encoding='utf-8'))
    with (acceptance/'blind-review.csv').open(encoding='utf-8-sig',newline='') as file:
        records=list(csv.DictReader(file))
    rows=[]
    for record in records:
        reference=by_id[key[record['review_id']]['case_id']]
        rows.append(dict(review_id=record['review_id'],question=record['question'],answer=record['answer'],
            gold_answer=record['gold_answer'],required_facts=reference['required_facts'],gold_evidence=reference['gold_evidence'],
            citations=json.loads(record['citations'])))
    payload=dict(fingerprint=summary['fingerprint_sha256'],rows=rows,
        provenance=json.loads((dataset/'provenance.json').read_text(encoding='utf-8')))
    template=(Path(__file__).parent/'templates/blind_review.html').read_text(encoding='utf-8')
    destination=acceptance/'blind-review.html'
    if destination.exists():
        raise FileExistsError('Review page already exists')
    destination.write_text(template.replace('__REVIEW_DATA__',json.dumps(payload,ensure_ascii=False).replace('<','\\u003c')),encoding='utf-8')
    return dict(rows=len(rows),human_scores_generated=0)


def import_grades(dataset,acceptance,csv_path,output,*,allow_partial=False):
    _,cases,summary=validate_dataset(dataset)
    key=json.loads((acceptance/'grading-key.json').read_text(encoding='utf-8'))
    with csv_path.open(encoding='utf-8-sig',newline='') as file:
        rows=list(csv.DictReader(file))
    ids=[item.get('review_id') for item in rows]
    if len(set(ids))!=len(ids) or set(ids)!=set(key):
        raise ValueError('Review IDs must exactly cover the blind review set without duplicates')
    grades={};reviewers=set()
    for row in rows:
        correctness=row.get('answer_correct','').strip().lower()
        explanation=row.get('explainability_score','').strip()
        reviewer=row.get('reviewer','').strip()
        if not correctness and not explanation:
            if not allow_partial:
                raise ValueError('Human review is incomplete; blank scores must remain missing')
            continue
        if correctness not in {'true','false'} or explanation not in {'1','2','3','4','5'} or not reviewer:
            raise ValueError('A real reviewer, boolean correctness and 1–5 explainability are required for every scored row')
        grades[row['review_id']]=(correctness=='true',int(explanation))
        reviewers.add(reviewer)
    if output.exists():
        raise FileExistsError('Human grade output must be new')
    output.mkdir(parents=True)
    report=dict(dataset=summary,human_reviewers=sorted(reviewers),scored_rows=len(grades),total_rows=len(rows),coverage=len(grades)/len(rows),modes={})
    for mode in sorted({item['mode'] for item in key.values()}):
        predictions=read_jsonl(acceptance/f'{mode}.jsonl')
        by_id={item['id']:item for item in predictions}
        for review_id,reference in key.items():
            if reference['mode']==mode and review_id in grades:
                correct,explain=grades[review_id]
                by_id[reference['case_id']].update(answer_correct=correct,explainability_score=explain)
        report['modes'][mode]=score_predictions(cases,predictions)
        (output/f'{mode}.jsonl').write_text(''.join(json.dumps(item,ensure_ascii=False)+'\n' for item in predictions),encoding='utf-8')
    (output/'human-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['export','score'])
    parser.add_argument('--dataset',type=Path,default=Path('../evaluation/public-v2'))
    parser.add_argument('--acceptance-dir',type=Path,required=True)
    parser.add_argument('--review-csv',type=Path)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--allow-partial',action='store_true')
    args=parser.parse_args()
    if args.action=='export':
        print(export_page(args.dataset,args.acceptance_dir))
    else:
        if not args.review_csv or not args.output_dir:
            parser.error('Scoring requires --review-csv and a new --output-dir')
        report=import_grades(args.dataset,args.acceptance_dir,args.review_csv,args.output_dir,allow_partial=args.allow_partial)
        print(dict(scored=report['scored_rows'],coverage=report['coverage']))
