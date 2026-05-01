# GoldenSetDoctor

**Find broken eval cases before they break your AI release decisions.**

GoldenSetDoctor, or GSD, is a local-first CLI for auditing the health of LLM evaluation datasets, golden sets, and AI test suites.

Before you trust an eval score, inspect the eval set behind it. GSD looks for duplicate scenarios, leaked answers, weak expected answers, ambiguous prompts, and other signals that make an eval suite noisy or unsafe to use for release decisions.

GSD is not an eval runner or hosted eval platform. It is a companion tool for teams already using Braintrust, LangSmith, Promptfoo, DeepEval, spreadsheets, JSONL files, or custom eval harnesses.

## Current Maturity

GSD is currently a local CLI prototype with meaningful working functionality. It can scan JSONL eval sets, call an LLM through LiteLLM, generate a machine-readable run artifact, and render a static HTML report.

The next milestone is to productize the prototype into a credible public devtool: clearer packaging, stable issue codes, scoring, release-readiness recommendations, CI gating, tests, and a more polished report.

## What It Checks Today

GSD can inspect a JSONL eval set for:

- **Near-duplicates**: repeated scenarios that can inflate scores and hide coverage gaps.
- **Reference leakage**: expected answers that are derivable from supplied reference `.txt` or `.md` documents.
- **Rubric and expected-answer issues**: missing expected answers, placeholder text, very short or very long expected answers, subjective prompts, time-sensitive phrasing, ambiguous pronouns, and multi-intent inputs.
- **Intent buckets**: LLM-generated `topic|slot|scope` groupings that make duplicate detection easier to audit.
- **Open-book cases**: items with `context_url` can be respected so intentional open-book examples are not counted as leakage.

GSD produces:

- `run.json`, a machine-readable scan artifact with counts, clusters, leakage matches, rubric findings, timings, and call stats.
- `report.html`, a static report with KPI cards, duplicate clusters, leakage matches, rubric issues, intent buckets, and per-item intent keys.
- Optional autofix output through `apply`, currently focused on limited mechanical cleanup such as duplicate consolidation and marking leakage cases as open-book.

## What It Cannot Conclude Alone

GSD is intentionally honest about what can and cannot be diagnosed from the eval set by itself.

From a dataset alone, GSD cannot certify:

- whether expected answers are factually correct against the current source of truth
- whether the eval set represents real production traffic
- whether cases catch historically important regressions
- whether a judge or grading policy is reliable
- whether a prompt, model, agent, or RAG pipeline is ready to ship
- whether a case is legally, medically, financially, or policy-compliance complete

Those checks require additional context such as product docs, policy docs, production logs, historical eval runs, model outputs, and human/domain review.

## Quick Start

### Requirements

- Python 3.10+
- An API key for a LiteLLM-supported model provider, such as OpenAI or Azure OpenAI

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Set a provider key:

```bash
export OPENAI_API_KEY=sk-...
```

Run a scan on the included sample:

```bash
python3 -m gsd.cli scan ./examples/dataset_v1.jsonl \
  --refs ./examples/docs \
  --out run.json \
  --model gpt-4o-mini \
  --pair-mode bucket-verify \
  --dup-thresh 0.6 \
  --leak-thresh 0.6 \
  --progress
```

Generate the report:

```bash
python3 -m gsd.cli report ./run.json --html report.html
```

Open `report.html` in your browser.

## CLI

```bash
python3 -m gsd.cli scan DATASET_JSONL [options]
python3 -m gsd.cli report RUN_JSON --html report.html
python3 -m gsd.cli apply RUN_JSON --dataset DATASET_JSONL --out dataset_v2.jsonl --changelog CHANGELOG.md
```

The package is not yet configured with a console script. A future packaging pass will add:

```bash
gsd scan ...
gsd report ...
gsd apply ...
```

### Important Scan Options

- `--model`: LLM model ID, such as `gpt-4o-mini` or an Azure deployment name.
- `--pair-mode`: duplicate strategy: `all`, `bucket`, or `bucket-verify`.
- `--dup-thresh`: confidence threshold for duplicate pair verification.
- `--leak-thresh`: confidence threshold for leakage detection.
- `--leak-topk`: number of candidate reference sentences to judge per item.
- `--respect-open-book/--no-respect-open-book`: skip or count leakage for items with `context_url`.
- `--rubric/--no-rubric`: enable or disable rubric linting.
- `--rubric-llm/--no-rubric-llm`: enable or disable LLM-based rubric checks.
- `--progress/--no-progress`: show or hide progress bars.

## Demo Datasets

### SQuAD v1.1 Subset

```bash
curl -L -o /tmp/squad_dev_v1.1.json https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v1.1.json
python3 tools/convert_squad.py /tmp/squad_dev_v1.1.json examples/squad/dataset_squad50.jsonl examples/squad/refs

python3 -m gsd.cli scan examples/squad/dataset_squad50.jsonl \
  --refs examples/squad/refs \
  --out run_squad.json \
  --model gpt-4o-mini \
  --pair-mode bucket-verify \
  --dup-thresh 0.6 \
  --leak-thresh 0.6 \
  --progress

python3 -m gsd.cli report run_squad.json --html report_squad.html
```

SQuAD items include `context_url`, so leakage is ignored by default when `--respect-open-book` is enabled.

### Office Synthetic Eval

```bash
python3 tools/make_office_eval.py

python3 -m gsd.cli scan examples/office_eval/dataset_office40.jsonl \
  --refs examples/office_eval/refs \
  --out run_office.json \
  --model gpt-4o-mini \
  --pair-mode bucket-verify \
  --dup-thresh 0.65 \
  --leak-thresh 0.6 \
  --progress

python3 -m gsd.cli report run_office.json --html report_office.html
```

The Office dataset intentionally includes duplicates, leakage, and rubric smells so the report has visible findings.

## Dataset Format

GSD currently expects JSONL. Each line should be one eval case.

Minimum useful schema:

```json
{
  "id": "Q01",
  "input": "User question or task",
  "expected": "Reference answer or expected behavior",
  "accepted": ["Alternative acceptable answer"],
  "context_url": "refs/policy.md",
  "tags": {"product": "Excel"}
}
```

Recommended future schema:

```json
{
  "id": "case_001",
  "input": "User question or task",
  "expected": "Expected behavior or answer",
  "rubric": "Criteria for a good answer",
  "accepted": ["Acceptable alternative"],
  "context_url": "refs/policy.md",
  "tags": {
    "intent": "refund_request",
    "product_area": "billing",
    "difficulty": "medium"
  },
  "source": "production",
  "severity": "high",
  "owner": "ai-platform",
  "last_reviewed": "2026-05-01",
  "gating": true
}
```

## How It Works

1. GSD loads JSONL eval cases and extracts each item input and expected answer.
2. It asks an LLM for conservative intent keys so similar cases can be grouped.
3. It clusters possible duplicates within those buckets, optionally verifying pairs for higher precision.
4. It compares expected answers against reference document sentences to detect possible leakage.
5. It runs heuristic and optional LLM rubric checks for missing, weak, ambiguous, or hard-to-grade items.
6. It writes `run.json` and renders a static `report.html`.

LLM calls use temperature `0.0` by default. Responses are cached locally under `.run/llm_cache.jsonl` to reduce cost and make reruns faster.

## Reading The Report

The current report includes:

- overall status based on duplicate members, leakage, and rubric errors
- item count and issue counts
- near-duplicate clusters with canonical items and member variants
- leakage matches with source file, confidence, reason, and snippet
- rubric findings with severity, code, reason, and suggested fix
- intent buckets and per-item intent keys for auditability

The report is static HTML and can be shared as a standalone artifact.

## Speed And Cost Tips

- Prefer `--pair-mode bucket-verify` for a practical balance of speed and precision.
- Use `--pair-mode bucket` for faster exploratory runs.
- Keep `--respect-open-book` enabled when your dataset intentionally includes `context_url`.
- Use `--leak-topk` to limit how many reference sentences are judged per item.
- Re-run scans without clearing `.run/llm_cache.jsonl` when you want cached LLM responses.

To force fresh judging:

```bash
rm -rf .run
```

## Roadmap

Near-term productization:

- Rewrite and maintain clear product documentation.
- Add `pyproject.toml` and a `gsd` console entrypoint.
- Add `gsd version`.
- Add focused tests and GitHub Actions.
- Introduce a stable issue taxonomy such as `GSD001`, `GSD002`, and so on.
- Add an Eval Fitness Score and release-readiness recommendation.
- Redesign the report around an executive summary, issue table, fix plan, and caveats.
- Add `gsd gate` with configurable thresholds for CI.

Later directions:

- CSV, Promptfoo, DeepEval, Braintrust, and LangSmith import/export adapters.
- A GitHub Action and optional PR comment summary.
- Context-aware checks for production representativeness, source-of-truth correctness, and historical sensitivity.

## Non-Goals For v0.1

GSD is not trying to become a hosted platform in v0.1. The near-term focus is a polished local CLI, useful reports, stable outputs, and CI-friendly gating.

Out of scope for v0.1:

- hosted dashboard
- database backend
- authentication or user accounts
- enterprise RBAC, SSO, or SOC2 workflows
- full eval-platform replacement
- automatic semantic rewriting of eval cases
- model-output scoring platform

## Troubleshooting

- Provider errors: confirm the right environment variables are set for your LiteLLM backend.
- Unexpected import errors: make sure dependencies are installed with `python3 -m pip install -r requirements.txt`.
- Stale LLM behavior: remove `.run` to clear the local cache.
- Shell paste issues: run commands without inline comments if your shell treats them literally.

## License

MIT
