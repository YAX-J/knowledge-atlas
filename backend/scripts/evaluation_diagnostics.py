"""Read frozen predictions/model grades and export offline development diagnostics.

No providers or database imports. Flags describe observable gaps, not human grades
or proven causal explanations. Historical answer exports cannot reconstruct the
exact prompt pool, so retrieval-pool gaps and answer omissions stay distinct.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from scripts.evaluate_dataset import _evidence_key, read_jsonl, validate_dataset


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def missing(gold, evidence):
    keys = {_evidence_key(item) for item in evidence}
    return [item for item in gold if _evidence_key(item) not in keys]


def passage(root, evidence):
    path = (root/evidence['source']).resolve()
    if not path.is_relative_to((root/'corpus').resolve()):
        raise ValueError('Evidence outside corpus')
    lines = path.read_text(encoding='utf-8').splitlines()
    start, end = evidence['start_line'], evidence['end_line']
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        raise ValueError('Evidence lines invalid')
    if not evidence['quote'] or evidence['quote'] not in '\n'.join(lines[start-1:end]):
        raise ValueError('Evidence quote invalid')
    return dict(quote=evidence['quote'], context='\n'.join(lines[max(0,start-4):min(len(lines),end+3)]))


def diagnose(case, prediction, quality, support):
    gold = case['gold_evidence']
    pool = prediction['retrieved_evidence']
    gaps = missing(gold, pool)
    flags = []
    if case['answerable']:
        if gaps:
            flags.append('retrieval_pool_gold_gap')
        if missing(gold, pool[:5]):
            flags.append('top5_gold_gap')
        if missing(gold, prediction['citations']):
            flags.append('citation_gold_gap')
        if quality['completeness']['choice'] in {'partial', 'missing'}:
            flags.append('model_flagged_incomplete')
        if quality['correctness']['choice'] == 'incorrect':
            flags.append('model_flagged_incorrect')
    elif prediction['supported']:
        flags.append('unanswerable_marked_supported')
    low = [name for name, value in quality.items()
           if value['confidence'] is None or value['confidence'] < .8]
    if low:
        flags.append('quality_low_confidence')
    uncertain = []
    for index, pair in enumerate(support):
        a, b = pair
        if a['choice'] != b['choice'] or any(
            item['confidence'] is None or item['confidence'] < .8 for item in pair
        ):
            uncertain.append(index)
    if uncertain:
        flags.append('citation_judge_uncertain')
    return dict(case_id=case['id'], category=case['category'], answerable=case['answerable'],
                question=case['question'], answer=prediction['answer'], supported=prediction['supported'],
                required_facts=case['required_facts'], gold_evidence=gold,
                missing_from_top5=missing(gold, pool[:5]), missing_from_pool=gaps,
                missing_from_citations=missing(gold, prediction['citations']),
                citations=prediction['citations'], quality=quality, quality_low_confidence=low,
                citation_judgments=support, citation_uncertain_units=uncertain, flags=flags,
                granularity='claim' if prediction.get('claims') is not None else 'legacy_answer',
                human_grade=None, causal_status='diagnostic flags; exact historical prompt pool unavailable')


def analyze(dataset, predictions, packet_dir, source_run, output):
    dataset, packet_dir, source_run, output = map(Path, (dataset, packet_dir, source_run, output))
    if output.exists():
        raise ValueError('Output directory must be new')
    _, cases, summary = validate_dataset(dataset)
    if summary['dataset_id'] == 'knowledge-atlas-holdout-v3':
        raise ValueError('Holdout must not be used for development diagnostics')
    cases = {item['id']: item for item in cases}
    packet = json.loads((packet_dir / 'packet.json').read_text(encoding='utf-8'))
    manifest = json.loads((packet_dir / 'packet-manifest.json').read_text(encoding='utf-8'))
    key = json.loads((packet_dir / 'grading-key.json').read_text(encoding='utf-8'))
    run = json.loads(source_run.read_text(encoding='utf-8'))
    if manifest['dataset'] != summary or digest(packet) != manifest['packet_sha256'] or run['packet_sha256'] != digest(packet):
        raise ValueError('Dataset/packet/run fingerprint mismatch')
    if run['status'] != 'succeeded' or run['human_grading_coverage'] != 0:
        raise ValueError('A completed model-only source run is required')
    if run['judge_config_sha256'] != digest(run['judge_config']):
        raise ValueError('Judge configuration fingerprint mismatch')
    by_review = {item['review_id']: item for item in packet}
    if len(by_review) != len(packet) or set(key) != set(by_review):
        raise ValueError('Grading key must cover every review exactly once')
    results = {}
    for result in run['results']:
        pair = (result['review_id'], result['part'])
        if pair in results or result['review_id'] not in by_review:
            raise ValueError('Duplicate or unknown judge result')
        results[pair] = result
    inputs = [dataset / 'manifest.json', dataset / 'cases.jsonl', source_run,
              *(packet_dir / name for name in ('packet.json', 'packet-manifest.json', 'grading-key.json'))]
    rows, covered = [], set()
    names = [Path(path).name for path in predictions]
    if len(names) != len(set(names)):
        raise ValueError('Prediction filenames must be unique')
    for path in map(Path, predictions):
        inputs.append(path)
        values = read_jsonl(path)
        if len(values) != len(cases) or {item['id'] for item in values} != set(cases):
            raise ValueError('Predictions must cover every case exactly once')
        for prediction in values:
            links = [identifier for identifier, link in key.items()
                     if link == dict(prediction=path.name, case_id=prediction['id'])]
            if len(links) != 1:
                raise ValueError('Prediction must map to exactly one anonymous review')
            identifier = links[0]
            review = by_review[identifier]
            case = cases[prediction['id']]
            if (review['answer'] != prediction['answer'] or review['question'] != case['question']
                    or review['answerable'] != case['answerable']
                    or review['reference_answer'] != case['gold_answer']
                    or review['required_facts'] != case['required_facts']):
                raise ValueError('Anonymous review content does not match prediction/reference')
            citations = [passage(dataset, item) for item in prediction['citations']]
            if prediction.get('claims') is None:
                units = [dict(claim=prediction['answer'], passages=citations)] if citations else []
            else:
                evidence = {item['id']: passage(dataset, item) for item in prediction['claim_evidence']}
                units = [dict(claim=claim['text'], passages=[evidence[identifier] for identifier in claim['citation_ids']])
                         for claim in prediction['claims'] if claim['status'] == 'supported']
            if review['units'] != units or review['supported'] != prediction['supported']:
                raise ValueError('Anonymous support units do not match prediction citations')
            pairs = [(results[(identifier, f'support-{index}-forward')]['answers']['relation'],
                      results[(identifier, f'support-{index}-reversed')]['answers']['relation'])
                     for index in range(len(review['units']))]
            row = diagnose(case, prediction, results[(identifier, 'quality')]['answers'], pairs)
            row.update(method=path.stem, review_id=identifier)
            rows.append(row)
            covered.add(identifier)
    expected = {(review['review_id'], part)
                for review in packet for part in ['quality', *(
                    f'support-{i}-{order}' for i in range(len(review['units'])) for order in ('forward', 'reversed'))]}
    if covered != set(by_review) or set(results) != expected:
        raise ValueError('All packet reviews and their exact judge jobs must be covered')
    methods = {}
    for name in names:
        items = [row for row in rows if row['method'] == Path(name).stem]
        methods[Path(name).stem] = dict(answers=len(items), flags=dict(Counter(flag for row in items for flag in row['flags'])))
    report = dict(protocol='offline-development-diagnostics-v1', dataset=summary, methods=methods,
                  rows=len(rows), human_grading_coverage=0, provider_requests_this_analysis=0,
                  source_requests=run['reserved_requests'], source_judge=run['judge_config'],
                  input_sha256={path.resolve().relative_to(Path(__file__).resolve().parents[2]).as_posix()
                      if path.resolve().is_relative_to(Path(__file__).resolve().parents[2]) else path.name:
                      hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
                  limitations=['Flags are not human grades or established root causes.',
                               'Top5 evidence recall differs from the full retrieved pool and actual prompt pool.',
                               'Reference facts are Agent-authored; no holdout cases analyzed.'])
    output.mkdir(parents=True, exist_ok=False)
    (output / 'per-answer.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    (output / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--predictions', type=Path, nargs='+', required=True)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--source-run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.dataset, args.predictions, args.packet, args.source_run, args.output)
    print(json.dumps(dict(rows=report['rows'], provider_requests_this_analysis=0)))


if __name__ == '__main__':
    main()
