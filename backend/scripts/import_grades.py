"""Import actual reviewer labels without inventing unfilled scores."""

import argparse
import csv
import json
from pathlib import Path

from scripts.evaluate_dataset import read_jsonl, score_predictions, validate_dataset


def import_grades(*, dataset: Path, acceptance: Path, review_csv: Path, output: Path):
    _, cases, summary = validate_dataset(dataset)
    key = json.loads((acceptance / "grading-key.json").read_text(encoding="utf-8"))
    with review_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    ids = [row["review_id"] for row in rows]
    if len(ids) != len(set(ids)) or set(ids) != set(key):
        raise ValueError("Review rows must match every blind-review ID exactly once")
    labels = {}
    for row in rows:
        correct, score = row["answer_correct"].strip(), row["explainability_score"].strip()
        if (correct or score) and not row["reviewer"].strip():
            raise ValueError("Filled scores require a reviewer pseudonym")
        if correct and correct.lower() not in {"true", "false", "1", "0"}:
            raise ValueError("Answer correctness must be true/false/1/0 or blank")
        if score and score not in {"1", "2", "3", "4", "5"}:
            raise ValueError("Explainability score must be 1..5 or blank")
        labels[row["review_id"]] = {"answer_correct": correct.lower() in {"true", "1"} if correct else None,
                                     "explainability_score": int(score) if score else None}
    output.mkdir(parents=True, exist_ok=False)
    reports = {}
    for mode in ("keyword", "vector", "hybrid"):
        predictions = read_jsonl(acceptance / f"answers-{mode}.jsonl")
        by_case = {item["id"]: item for item in predictions}
        for review_id, target in key.items():
            if target["mode"] == mode:
                by_case[target["case_id"]].update(labels[review_id])
        reports[mode] = score_predictions(cases, predictions)
        (output / f"{mode}.jsonl").write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in predictions), encoding="utf-8")
    report = {"dataset": summary, "metrics": reports,
              "reviewed_rows": sum(any(value is not None for value in label.values()) for label in labels.values())}
    (output / "grading.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--acceptance-dir", type=Path, required=True)
    parser.add_argument("--review-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = import_grades(dataset=args.dataset, acceptance=args.acceptance_dir, review_csv=args.review_csv, output=args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
