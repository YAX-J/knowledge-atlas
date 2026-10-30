# Jev anonymous model evaluation

[简体中文](JEV_EVALUATION.zh-CN.md)

For Jev through OpenRouter, use the separate [OpenRouter guide](OPENROUTER_EVALUATION.md) and --provider openrouter. The direct TypeSafe key/model fields and --allow-jev-calls remain scoped to direct TypeSafe only.

Anonymous grading supports direct TypeSafe Jev, OpenRouter Jev and [native CF](CLOUDFLARE_EVALUATION.md); this page describes direct TypeSafe. Human coverage remains0%, and formal knowledge requires human review. The historical20-answer BM25 preflight plans54 requests with zero reservations/completions. No live judge calls or quality scores were produced during implementation. [ADR0072](adr/0072-cloudflare-judge-adapter.md) extends the Jev-only restriction of ADR0070; old experiments and human fields remain unchanged.

## Configuration

The following fields have been added to backend/.env and [.env.example](../backend/.env.example). The user supplies the key locally after development; never paste it into chat or commit .env.

```dotenv
TYPESAFE_API_KEY=
TYPESAFE_MODEL=jev-1.14.0
TYPESAFE_BASE_URL=https://api.typesafe.ai
TYPESAFE_TIMEOUT_SECONDS=60
```

The adapter uses existing httpx and the official [System One API](https://docs.typesafe.ai/api/system-one); no SDK install is required. Aliases are rejected, actual model identity checked, responses bounded to128 KiB and requests to24000 UTF-8 JSON bytes. No automatic retries are made. These guards do not establish token usage, accuracy or a cost estimate.

## Prepare and inspect without provider calls

Run from backend, using a new output directory for each experiment:

```powershell
.\.venv\Scripts\python.exe -m scripts.jev_evaluation prepare --dataset ../evaluation/public-v2 --predictions ../evaluation/results/2026-10-26-public-v2-run1/bm25.jsonl --output ../output/jev-my-run/packet
.\.venv\Scripts\python.exe -m scripts.jev_evaluation run --provider jev --packet ../output/jev-my-run/packet --output ../output/jev-my-run/preflight
```

Preparation requires each supplied method export to cover every dataset case and contain real answer text. It revalidates exact source lines/quotes, creates a shuffled packet and stores method/case mapping separately. The judge input omits method, generator model/confidence and case identity. Old flat exports retain `legacy_answer` granularity; new public acceptance exports include `claims` plus `claim_evidence` for claim-level checks. No old response is split into invented atomic claims.

Preflight hashes the packet, checks pinned model/input guards and writes `status=prepared`, planned requests, zero reservations/completions/model grades and human coverage0. It does not require a key. The example plans54 requests: one quality request per answer and two option-order checks per cited unit. The packet and its manifest must remain unchanged.

## Future explicitly authorized live run

This command is documented for a later authorized run, and was not executed this turn:

```powershell
.\.venv\Scripts\python.exe -m scripts.jev_evaluation run --provider jev --packet ../output/jev-my-run/packet --output ../output/jev-my-run/live --allow-jev-calls --max-requests 54
```

Use the preflight's actual planned count for another packet. Insufficient budgets or missing keys fail before transport. All attempts, including failures/unknown outcomes, are reserved on disk before a call; errors stop without automatic retry. An existing output cannot be overwritten or resumed. Jev reservations do not reset or consume the historical84-model/61-embedding ledger; each new Jev run requires its own explicit call authorization. No API, Worker, page reload or GET starts this evaluation.

## Interpretation

Correctness, required-fact coverage and abstention are distinct Choice questions using reference facts. Citation checks see only one claim and its cited context, never the reference answer. Source context includes up to3 lines around the exact quoted range. Both option orders are retained; disagreement or confidence below0.8 flags uncertainty rather than verifying a claim. The threshold is fixed by protocol and is not a project-calibrated accuracy estimate.

`run.json` contains typed decisions/probabilities, actual model, usage, packet hash, per-call reservations, granularity and uncertainty flags. Interpret these as model judgments. Do not copy them into human `answer_correct`/`explainability_score` fields or claim agreement with users. Reference annotations may be Agent-authored; they are not human grades. Jev provides no generated explanation text. Holdout-v3 stays separate: freeze the protocol before using it, and never tune ranking/prompts/thresholds on its outcomes. See the vendor's [citation example](https://docs.typesafe.ai/cookbooks/citation_check) and [known limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13).
