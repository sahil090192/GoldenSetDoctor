# gsd/cli.py
from __future__ import annotations
import json, os, sys, typer

if __package__ in (None, ""):
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from gsd.scan import scan_dataset, save_run
    from gsd.report import save_html
    from gsd.apply import apply_autofix
else:
    from .scan import scan_dataset, save_run
    from .report import save_html
    from .apply import apply_autofix

app = typer.Typer(help="Golden-Set Doctor (LLM-only, intent-bucketed)")

@app.command()
def scan(
    dataset: str = typer.Argument(..., help="Path to dataset JSONL"),
    refs: str = typer.Option("", "--refs", help="Folder with .txt/.md docs for leakage detection"),
    out: str = typer.Option("run.json", "--out", help="Output run JSON"),
    model: str = typer.Option("", "--model", help="LLM model id (e.g., gpt-4o-mini, azure/<deployment>). REQUIRED."),
    temperature: float = typer.Option(0.0, "--temperature", help="LLM temperature"),
    dup_thresh: float = typer.Option(0.6, "--dup-thresh", help="Pair verification threshold (bucket-verify)"),
    leak_thresh: float = typer.Option(0.6, "--leak-thresh", help="Leakage threshold"),
    respect_open_book: bool = typer.Option(True, "--respect-open-book/--no-respect-open-book",
                                           help="If true, do not count leakage for items with context_url"),
    progress: bool = typer.Option(True, "--progress/--no-progress", help="Show progress bars"),
    pair_mode: str = typer.Option("bucket-verify", "--pair-mode",
                                  help="Duplicates strategy: all | bucket | bucket-verify"),
):
    run = scan_dataset(
        dataset_path=dataset,
        refs_dir=(refs or None),
        model=model,
        temperature=temperature,
        dup_thresh=dup_thresh,
        leak_thresh=leak_thresh,
        respect_open_book=respect_open_book,
        progress=progress,
        pair_mode=pair_mode,
    )
    save_run(run, out)
    t = run.get("timings", {})
    s = run.get("stats", {})
    print(f"✓ Scan complete. dups={run['counts']['dup_members']} clusters={run['counts']['dup_clusters']} leakage={run['counts']['leakage']}")
    print(f"  pair_mode={pair_mode}  time: total={t.get('total_sec',0):.2f}s  (intent={t.get('intent_sec',0):.2f}s, dups={t.get('duplicates_sec',0):.2f}s, leak={t.get('leakage_sec',0):.2f}s)")
    print(f"  buckets={s.get('buckets',0)}  bucket_calls={s.get('bucket_calls',0)}  dup_pair_verifications={s.get('dup_pair_verifications',0)}")
    print(f"  pairs_total_est={s.get('dup_pairs_total','?')}  pairs_within_buckets={s.get('dup_pairs_within_buckets','?')}  leak_calls={s.get('leak_calls',0)}")
    print(f"  wrote {out}")

@app.command()
def report(run: str = typer.Argument(..., help="Path to run.json"),
           html: str = typer.Option("report.html", "--html", help="Output HTML path")):
    with open(run, "r", encoding="utf-8") as f:
        data = json.load(f)
    save_html(data, html)
    print(f"✓ Report written to {html}")

@app.command()
def apply(run: str = typer.Argument(..., help="Path to run.json"),
          dataset: str = typer.Option(..., "--dataset", help="Original dataset JSONL"),
          out: str = typer.Option("dataset_v2.jsonl", "--out", help="Output dataset JSONL (v2)"),
          changelog: str = typer.Option("CHANGELOG.md", "--changelog", help="Changelog path")):
    with open(run, "r", encoding="utf-8") as f:
        data = json.load(f)
    apply_autofix(data, dataset_path=dataset, out_dataset_path=out, changelog_path=changelog)
    print(f"✓ Applied fixes. Wrote {out} and {changelog}")

if __name__ == "__main__":
    app()
