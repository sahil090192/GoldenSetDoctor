# gsd/scan.py
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Dict, Any, List, Tuple
from tqdm import tqdm

from .utils import load_jsonl, item_input_text, item_expected_text, iter_doc_sentences
from .judge_llm import llm_cluster_duplicates, judge_leakage

def _build_dup_clusters(idx_clusters: List[List[int]], ids: List[str], inputs: List[str], expecteds: List[str]):
    dup_clusters = []
    dup_members = 0
    for cluster in idx_clusters:
        canon_idx = max(cluster, key=lambda i: len(expecteds[i]))
        members = [i for i in cluster if i != canon_idx]
        dup_members += len(members)
        dup_clusters.append({
            "canonical": ids[canon_idx],
            "canonical_input": inputs[canon_idx],
            "members": [ids[i] for i in members],
            "member_inputs": [inputs[i] for i in members],
        })
    return dup_clusters, dup_members

def scan_dataset(
    dataset_path: str,
    refs_dir: str | None = None,
    model: str = "",                 # REQUIRED LLM model
    temperature: float = 0.0,
    dup_thresh: float = 0.6,
    leak_thresh: float = 0.6,
    respect_open_book: bool = True,
    progress: bool = True,
) -> Dict[str, Any]:
    if not model:
        raise ValueError("model is required for LLM-only scan (pass --model).")

    ds_path = Path(dataset_path)
    items = load_jsonl(ds_path)
    ids = [it.get("id", f"it_{i}") for i, it in enumerate(items)]
    inputs = [item_input_text(it) for it in items]
    expecteds = [item_expected_text(it) for it in items]

    timings: Dict[str, float] = {}
    stats: Dict[str, Any] = {}

    # -------- duplicates via LLM --------
    t0 = time.time()
    idx_clusters, dup_stats = llm_cluster_duplicates(
        inputs, model=model, threshold=dup_thresh, temperature=temperature, progress=progress
    )
    timings["duplicates_sec"] = time.time() - t0
    stats["dup_pairs"] = dup_stats["pairs"]
    stats["dup_pairs_kept"] = dup_stats["accepted"]
    dup_clusters, dup_members = _build_dup_clusters(idx_clusters, ids, inputs, expecteds)

    # -------- leakage via LLM --------
    leakage_hits: List[Dict[str, Any]] = []
    leak_calls = 0
    t1 = time.time()
    if refs_dir:
        sentences = iter_doc_sentences(refs_dir)
        total_calls = len(expecteds) * max(1, len(sentences))
        bar = tqdm(total=total_calls, desc="Leakage checks", unit="call", leave=False, disable=not progress)
        for row_idx, exp in enumerate(expecteds):
            if respect_open_book and items[row_idx].get("context_url"):
                bar.update(len(sentences)); leak_calls += len(sentences)
                continue
            best_idx: int | None = None
            best_conf = -1.0
            best_reason = ""
            for si, s in enumerate(sentences):
                derived, conf, reason = judge_leakage(exp, s["text"], model=model, temperature=temperature)
                leak_calls += 1
                bar.update(1)
                if derived and conf > best_conf:
                    best_conf = conf
                    best_idx = si
                    best_reason = reason
            if best_idx is not None and best_conf >= leak_thresh:
                s = sentences[best_idx]
                leakage_hits.append({
                    "item_id": ids[row_idx],
                    "file": s["file"],
                    "snippet": s["text"],
                    "score": round(float(best_conf), 3),
                    "reason": best_reason,
                })
        bar.close()
    timings["leakage_sec"] = time.time() - t1
    stats["leak_calls"] = leak_calls

    timings["total_sec"] = timings.get("duplicates_sec", 0) + timings.get("leakage_sec", 0)

    run = {
        "dataset": str(ds_path.as_posix()),
        "refs_dir": refs_dir or "",
        "counts": {
            "items": len(items),
            "dup_clusters": len(dup_clusters),
            "dup_members": dup_members,
            "leakage": len(leakage_hits),
        },
        "dup_clusters": dup_clusters,
        "leakage": leakage_hits,
        "timings": timings,
        "stats": stats,
    }
    return run

def save_run(run: Dict[str, Any], out_path: str) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=2)
