import csv
import json
from pathlib import Path

import pytest

from scripts.render_experiments import render


def test_frozen_figures_preserve_missing_scores_and_provenance(tmp_path):
    pytest.importorskip("matplotlib")
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / "figures"
    result = render(retrieval=root / "evaluation/results/2026-10-24-v101/retrieval",
                    acceptance=root / "evaluation/results/2026-10-24-models", output=output)
    assert len(result["figures"]) == 5
    assert result["input_hash_protocol"] == "utf8-lf-v1"
    assert all(len(item["sha256"]) == 64 for item in result["inputs"])
    assert len(list(output.glob("*.svg"))) == 5
    for path in output.glob("*.svg"):
        assert all(line == line.rstrip() for line in path.read_text(encoding="utf-8").splitlines())
    with (output / "values.csv").open(encoding="utf-8", newline="") as handle:
        values = list(csv.DictReader(handle))
    missing = [row for row in values if row["figure"] == "answers" and row["series"] == "keyword" and row["category"] == "Citation F1"]
    assert missing[0]["value"] == ""  # not a fabricated zero
    assert json.loads((output / "provenance.json").read_text())["human_grading"].startswith("not included")
    with pytest.raises(FileExistsError):
        render(retrieval=root / "evaluation/results/2026-10-24-v101/retrieval",
               acceptance=root / "evaluation/results/2026-10-24-models", output=output)
