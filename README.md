# Golden-Set Doctor (GSD)

> Keep your LLM evaluation golden sets **honest and healthy**.  
> Detect **near-duplicates**, **reference leakage**, and **rubric issues**.  
> Generate **fix plans** and **gate CI** so noisy evals don’t ship.

---

## Why this exists

Golden sets drift. Teams unknowingly evaluate on:

- The **same question phrased 5 ways** (inflates scores)
- **Leaked answers** copied from reference docs (open-book when you think it’s closed-book)
- **Weak rubrics** (missing/too short/too long/ambiguous)

GSD finds these issues, explains them, and proposes safe fixes.

---

## What it does (today)

- **LLM-only duplicate detection**
  - Intent **bucketing** (`topic|slot|scope`) to avoid over-grouping
  - **Bucket clustering** with optional **pair verification** for high precision
- **Leakage detection**
  - Sentence-level LLM judge: “is expected answer derivable from this reference?”
  - *Respect open-book* option ignores items that already have `context_url`
- **Readable HTML report**
  - KPI cards + near-duplicate clusters + leakage table
  - **Intent buckets** and **per-item intent keys** to audit bucketing
- **Run artifact (`run.json`)**: counts, timings, call stats, clusters, leakage, intents

> Coming next: **rubric lint** (missing/too short/too long/ambiguous) and **apply fixes** (merge dupes, mark open-book). CLI `apply` is already wired.

---

## Quick start

### Requirements

- Python **3.10+**
- Provider key for an OpenAI-compatible model (via `litellm`) — e.g. `gpt-4o-mini`, Azure OpenAI, etc.

### Install

```bash
python3 -m pip install -r requirements.txt

Configure key
export OPENAI_API_KEY=sk-...   # or provider-specific envs supported by litellm

Run on the included sample (Git/GitHub 25)
python3 -m gsd.cli scan ./examples/dataset_v1.jsonl \
  --refs ./examples/docs --out run.json \
  --model gpt-4o-mini --pair-mode bucket-verify --dup-thresh 0.6 --leak-thresh 0.6 --progress

python3 -m gsd.cli report ./run.json --html report.html && open report.html

Demo datasets
SQuAD v1.1 (50-item subset)
curl -L -o /tmp/squad_dev_v1.1.json https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v1.1.json
python3 tools/convert_squad.py /tmp/squad_dev_v1.1.json examples/squad/dataset_squad50.jsonl examples/squad/refs

python3 -m gsd.cli scan examples/squad/dataset_squad50.jsonl \
  --refs examples/squad/refs --out run_squad.json \
  --model gpt-4o-mini --pair-mode bucket-verify --dup-thresh 0.6 --leak-thresh 0.6 --progress

python3 -m gsd.cli report run_squad.json --html report_squad.html && open report_squad.html

SQuAD items include context_url, so leakage is 0 with --respect-open-book (default).

Office / OneDrive / Teams synthetic (covers dupes + leakage + rubric smells)
python3 tools/make_office_eval.py

python3 -m gsd.cli scan examples/office_eval/dataset_office40.jsonl \
  --refs examples/office_eval/refs --out run_office.json \
  --model gpt-4o-mini --pair-mode bucket-verify --dup-thresh 0.65 --leak-thresh 0.6 --progress

python3 -m gsd.cli report run_office.json --html report_office.html && open report_office.html


CLI
python3 -m gsd.cli scan DATASET_JSONL [options]
python3 -m gsd.cli report RUN_JSON --html report.html
python3 -m gsd.cli apply RUN_JSON --dataset DATASET_JSONL --out dataset_v2.jsonl --changelog CHANGELOG.md


Key options

--model (required): LLM id (e.g., gpt-4o-mini, Azure deployment name)

--pair-mode: all | bucket | bucket-verify

bucket: fastest (cluster per intent bucket; no pair checks)

bucket-verify: balance (verify pairs inside proposed groups)

all: slow (judge every pair)

--dup-thresh: confidence threshold for pair verification (0..1)

--leak-thresh: confidence threshold for leakage (0..1)

--respect-open-book/--no-respect-open-book: ignore/count items with context_url

--progress/--no-progress: show progress bars

Reading the report

Status: “Healthy” when dup members == 0 and leakage == 0

Dup clusters: canonical item + member variants

Leakage: item id, matched file, score, reason, snippet

Intent buckets: grouped view to confirm good separation (who/what/where/when/count/…)

Per-item intents: each question with its topic | slot | scope key

Output files

run.json (machine-readable):

{
  "counts": {"items": 50, "dup_clusters": 6, "dup_members": 6, "leakage": 0},
  "dup_clusters": [ ... ],
  "leakage": [ ... ],
  "intent": { "items": [...], "buckets": [...] },
  "timings": {"intent_sec": 49.9, "duplicates_sec": 10.6, "leakage_sec": 0.0, "total_sec": 60.5},
  "stats": { "intent_calls": 50, "buckets": 43, "bucket_calls": 7, "dup_pair_verifications": 7 }
}


report.html — static, PR-friendly summary page

How it works

Intent bucketing (N LLM calls) → conservative topic|slot|scope per query

Within-bucket clustering (B LLM calls) → group near-duplicates

(Optional) pair verification for each proposed group edge

Leakage → LLM checks if the expected answer is derivable from reference sentences

With --respect-open-book, items with context_url are skipped

Deterministic by default: temperature=0.0 and on-disk cache .run/llm_cache.jsonl.

Speed & cost tips

Prefer --pair-mode bucket-verify (default) for precision; bucket for the fastest runs

Keep --respect-open-book when datasets include context_url

Re-runs are cheap thanks to .run/llm_cache.jsonl

Force fresh judging:

find gsd -name "__pycache__" -type d -prune -exec rm -rf {} +
rm -rf .run

Troubleshooting

TypeError: unexpected keyword → replace the indicated module with the latest drop-in

ImportError: cannot import name judge_leakage → update gsd/judge_llm.py to the version that defines it, then clear caches

zsh: parse error near ')' → remove inline comments from pasted commands or run setopt interactivecomments

Provider errors → set the correct env var(s) for your litellm backend; confirm the model/deployment id

Roadmap

Rubric lint: missing expected, too short/too long, ambiguous/multi-intent

Apply fixes: merge dupes → move variants to accepted; mark leakage as open-book

CI gate: thresholds in gsd.yml + GitHub/Azure templates

Leakage preselector (top-K sentences) and optional concurrency

Contributing / Add a dataset

JSONL schema:

{
  "id": "Q01",
  "input": "question",
  "expected": "reference answer",
  "accepted": ["alt answer 1"],
  "context_url": "path/optional",
  "tags": {"product":"Excel"}
}


Put refs (.txt/.md) under examples/<name>/refs

Add generators under tools/ for reproducible samples

License

MIT © You & Contributors