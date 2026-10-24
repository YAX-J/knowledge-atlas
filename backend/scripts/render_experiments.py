"""Render reproducible figures from frozen results; never call providers or grade people."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import platform


def render(*, retrieval: Path, acceptance: Path, output: Path) -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    modes = ("keyword", "vector", "hybrid")
    call_modes = ("static", "single_step", "tools")
    inputs = [retrieval / f"{mode}.metrics.json" for mode in modes]
    inputs += [acceptance / f"calls-{mode}.metrics.json" for mode in call_modes]
    inputs += [acceptance / f"answers-{mode}.metrics.json" for mode in modes]
    inputs += [acceptance / "acceptance.json"]
    data = [json.loads(path.read_text(encoding="utf-8")) for path in inputs]
    if data[-1]["status"] != "succeeded":
        raise ValueError("Only a successful acceptance can be plotted")
    output.mkdir(parents=True, exist_ok=False)
    colors = ("#a9b7bd", "#2a6570", "#a9345f")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "svg.fonttype": "none",
                         "svg.hashsalt": "knowledge-atlas-experiments-v1"})
    rows = []

    def bars(name, title, labels, series, *, unit="Score", maximum=1.08, note=""):
        fig, ax = plt.subplots(figsize=(9, 4.8), layout="constrained")
        x = np.arange(len(labels))
        width = .76 / len(series)
        for i, (label, values) in enumerate(series):
            positions = x + (i - (len(series) - 1) / 2) * width
            ax.bar(positions, [np.nan if value is None else value for value in values], width,
                   color=colors[i], label=label)
            for position, value in zip(positions, values, strict=True):
                if value is None:
                    ax.text(position, .02, "N/A", rotation=90, ha="center", fontsize=8)
            for category, value in zip(labels, values, strict=True):
                rows.append({"figure": name, "series": label, "category": category, "value": value})
        ax.set_xticks(x, labels)
        ax.set_ylim(0, maximum)
        ax.set_ylabel(unit)
        ax.set_title(title, loc="left", fontweight="bold", pad=16)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
        ax.legend(loc="upper center", bbox_to_anchor=(.5, -.1), ncol=3, frameon=False)
        fig.suptitle(note, fontsize=9, color="#526368", y=.01)
        for suffix in ("png", "svg"):
            target = output / f"{name}.{suffix}"
            fig.savefig(target, dpi=180, bbox_inches="tight", metadata={"Date": None} if suffix == "svg" else None)
            if suffix == "svg":
                target.write_text("\n".join(line.rstrip() for line in target.read_text(encoding="utf-8").splitlines()) + "\n",
                                  encoding="utf-8", newline="\n")
        plt.close(fig)

    bars("retrieval", "Frozen retrieval: evidence Recall@K", ["@1", "@3", "@5"],
         [(mode, [data[i]["retrieval"][f"evidence_recall_at_{k}"] for k in (1, 3, 5)])
          for i, mode in enumerate(modes)], note="40 synthetic questions; 36 answerable. Formal-entity retrieval, not raw chunk RAG.")
    bars("calls", "Cross-file analysis: static vs single-step vs tools",
         ["Exact decision", "Target precision", "Target recall", "Unresolved accuracy"],
         [(mode, [data[i + 3]["metrics"][key] for key in (
             "exact_decision_accuracy", "target_precision", "target_recall", "unresolved_accuracy")])
          for i, mode in enumerate(call_modes)],
         note="50 synthetic cases / 10 languages; one run. Candidate generation is shared, not compiler ground truth.")
    languages = sorted(data[3]["metrics"]["by_language"])
    bars("languages", "Exact decisions by language (five cases each)", languages,
         [(mode, [data[i + 3]["metrics"]["by_language"][lang] for lang in languages])
          for i, mode in enumerate(call_modes)], note="Small constructed corpus; no significance or generalization claim.")
    bars("answers", "Frozen-evidence answer replay: automatic checks",
         ["Support/refusal", "Citation F1", "Required facts"],
         [(mode, [data[i + 6]["answers"]["supported_or_refusal_accuracy"],
                  data[i + 6]["citations"]["f1"], data[i + 6]["answers"]["required_fact_coverage"]])
          for i, mode in enumerate(modes)],
         note="NOT human answer accuracy. Manual correctness and explainability remain ungraded.")
    latency = [[sum(run["latency_ms"] for run in data[i + 3]["runs"]) / len(data[i + 3]["runs"])] for i in range(3)]
    bars("latency", "Mean cross-file analysis latency per repository", ["10 repositories"],
         list(zip(call_modes, latency, strict=True)), unit="Milliseconds", maximum=max(v[0] for v in latency) * 1.2,
         note="Static: no provider. Single-step: one request/repo. Tools: two requests/repo in this run.")
    with (output / "values.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("figure", "series", "category", "value"))
        writer.writeheader()
        writer.writerows(rows)
    metadata = {"input_hash_protocol": "utf8-lf-v1",
                "renderer": {"python": platform.python_version(), "matplotlib": matplotlib.__version__},
                "inputs": [{"file": str(path.name), "sha256": hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()} for path in inputs],
                "figures": ["retrieval", "calls", "languages", "answers", "latency"],
                "human_grading": "not included; use import_grades with real reviewer labels",
                "ablation": "vector (graph off) vs fixed hybrid (graph on); no weight search or new embedding calls"}
    (output / "provenance.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval-dir", type=Path, required=True)
    parser.add_argument("--acceptance-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(render(retrieval=args.retrieval_dir, acceptance=args.acceptance_dir, output=args.output_dir), indent=2))


if __name__ == "__main__":
    main()
