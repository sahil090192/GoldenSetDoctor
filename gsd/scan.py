# gsd/scan.py
from __future__ import annotations
import json, time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Any, List
from tqdm import tqdm

from .utils import load_jsonl, item_input_text, item_expected_text, iter_doc_sentences
from .judge_llm import (
    intent_keys, bucket_cluster, judge_duplicate, judge_leakage
)

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

def _clusters_from_buckets(buckets, inputs, *, model, temperature, verify_pairs, dup_thresh, progress):
    global_clusters: List[List[int]] = []
    stats = {"buckets": len(buckets), "bucket_calls": 0, "dup_pair_verifications": 0}

    for _key, idxs in tqdm(list(buckets.items()), desc="Buckets", unit="bucket", leave=False, disable=not progress):
        if len(idxs) <= 1:
            continue
        local_items = [inputs[i] for i in idxs]
        cluster_local = bucket_cluster(local_items, model=model, temperature=temperature)
        stats["bucket_calls"] += 1
        if not cluster_local:
            continue

        if verify_pairs:
            # verify edges with pairwise judge inside each proposed group
            from itertools import combinations
            parent = {i: i for i in idxs}
            rank = {i: 0 for i in idxs}
            def find(x):
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x
            def union(a, b):
                ra, rb = find(a), find(b)
                if ra == rb: return
                if rank[ra] < rank[rb]: parent[ra] = rb
                elif rank[ra] > rank[rb]: parent[rb] = ra
                else: parent[rb] = ra; rank[ra] += 1

            for group in cluster_local:
                g_abs = [idxs[i] for i in group]
                for a, b in combinations(g_abs, 2):
                    dup, conf, _ = judge_duplicate(inputs[a], inputs[b], model=model, temperature=temperature)
                    stats["dup_pair_verifications"] += 1
                    if dup and conf >= dup_thresh:
                        union(a, b)
            comp = defaultdict(list)
            for i in idxs:
                comp[find(i)].append(i)
            for v in comp.values():
                if len(v) >= 2:
                    global_clusters.append(sorted(v))
        else:
            for group in cluster_local:
                global_clusters.append(sorted([idxs[i] for i in group]))

    # merge overlapping groups
    if global_clusters:
        uf_parent = list(range(len(global_clusters)))
        uf_rank = [0]*len(global_clusters)
        def findg(x):
            while uf_parent[x] != x:
                uf_parent[x] = uf_parent[uf_parent[x]]
                x = uf_parent[x]
            return x
        def uniong(a, b):
            ra, rb = findg(a), findg(b)
            if ra == rb: return
            if uf_rank[ra] < uf_rank[rb]: uf_parent[ra] = rb
            elif uf_rank[ra] > uf_rank[rb]: uf_parent[rb] = ra
            else: uf_parent[rb] = ra; uf_rank[ra] += 1
        for i in range(len(global_clusters)):
            si = set(global_clusters[i])
            for j in range(i+1, len(global_clusters)):
                if si.intersection(global_clusters[j]):
                    uniong(i, j)
        comp = defaultdict(list)
        for i in range(len(global_clusters)):
            comp[findg(i)].extend(global_clusters[i])
        merged = []
        for v in comp.values():
            s = sorted(set(v))
            if len(s) >= 2:
                merged.append(s)
        global_clusters = merged

    return global_clusters, stats

def scan_dataset(
    dataset_path: str,
    refs_dir: str | None = None,
    model: str = "",
    temperature: float = 0.0,
    dup_thresh: float = 0.6,
    leak_thresh: float = 0.6,
    respect_open_book: bool = True,
    progress: bool = True,
    pair_mode: str = "bucket-verify",  # all | bucket | bucket-verify
) -> Dict[str, Any]:
    if not model:
        raise ValueError("model is required (pass --model).")

    ds_path = Path(dataset_path)
    items = load_jsonl(ds_path)
    ids = [it.get("id", f"it_{i}") for i, it in enumerate(items)]
    inputs = [item_input_text(it) for it in items]
    expecteds = [item_expected_text(it) for it in items]

    timings: Dict[str, float] = {}
    stats: Dict[str, Any] = {}

    # 1) Intent keys
    t0 = time.time()
    keys, meta = intent_keys(inputs, model=model, temperature=temperature, progress=progress)
    timings["intent_sec"] = time.time() - t0
    stats["intent_calls"] = len(inputs)

    buckets: Dict[str, List[int]] = defaultdict(list)
    for i, k in enumerate(keys):
        buckets[k].append(i)
    stats["buckets"] = len(buckets)

    # Build intent structures for the run artifact & report
    intent_items = []
    for i, k in enumerate(keys):
        m = meta[i] if i < len(meta) else {}
        intent_items.append({
            "id": ids[i],
            "input": inputs[i],
            "key": k,
            "topic": m.get("topic", ""),
            "slot": m.get("slot", ""),
            "scope": m.get("scope", "")
        })
    intent_buckets = []
    for k, idxs in buckets.items():
        intent_buckets.append({
            "key": k,
            "size": len(idxs),
            "members": [{"id": ids[i], "input": inputs[i]} for i in idxs]
        })
    # sort buckets by size desc, then key
    intent_buckets.sort(key=lambda b: (-b["size"], b["key"]))

    # 2) Duplicates
    t1 = time.time()
    if pair_mode == "all":
        from itertools import combinations
        parent = list(range(len(inputs))); rank=[0]*len(inputs)
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra == rb: return
            if rank[ra] < rank[rb]: parent[ra] = rb
            elif rank[ra] > rank[rb]: parent[rb] = ra
            else: parent[rb] = ra; rank[ra] += 1
        calls = 0
        bar = tqdm(total=(len(inputs)*(len(inputs)-1))//2, desc="Duplicate pairs", unit="pair", leave=False, disable=not progress)
        for a, b in combinations(range(len(inputs)), 2):
            dup, conf, _ = judge_duplicate(inputs[a], inputs[b], model=model, temperature=temperature)
            calls += 1; bar.update(1)
            if dup and conf >= dup_thresh:
                union(a, b)
        bar.close()
        comp = defaultdict(list)
        for i in range(len(inputs)): comp[find(i)].append(i)
        idx_clusters = [sorted(v) for v in comp.values() if len(v) >= 2]
        stats["dup_pair_verifications"] = calls
        stats["dup_pairs_total"] = (len(inputs)*(len(inputs)-1))//2
    else:
        verify = (pair_mode == "bucket-verify")
        idx_clusters, bstats = _clusters_from_buckets(
            buckets, inputs, model=model, temperature=temperature,
            verify_pairs=verify, dup_thresh=dup_thresh, progress=progress
        )
        stats.update(bstats)
        total_pairs = (len(inputs)*(len(inputs)-1))//2
        within_bucket_pairs = sum(len(v)*(len(v)-1)//2 for v in buckets.values())
        stats["dup_pairs_total"] = total_pairs
        stats["dup_pairs_within_buckets"] = within_bucket_pairs
    timings["duplicates_sec"] = time.time() - t1

    dup_clusters, dup_members = _build_dup_clusters(idx_clusters, ids, inputs, expecteds)

    # 3) Leakage (count only actual calls)
    leakage_hits: List[Dict[str, Any]] = []
    leak_calls = 0
    t2 = time.time()
    if refs_dir:
        sentences = iter_doc_sentences(refs_dir)
        # Only judge items that aren't open-book when respect_open_book=True
        idx_to_check = [
            i for i in range(len(expecteds))
            if not (respect_open_book and items[i].get("context_url"))
        ]
        total_calls = len(idx_to_check) * max(1, len(sentences))
        bar = tqdm(total=total_calls, desc="Leakage checks", unit="call", leave=False, disable=not progress)
        for row_idx in idx_to_check:
            exp = expecteds[row_idx]
            best_idx = None; best_conf = -1.0; best_reason = ""
            for si, s in enumerate(sentences):
                derived, conf, reason = judge_leakage(exp, s["text"], model=model, temperature=temperature)
                leak_calls += 1; bar.update(1)
                if derived and conf > best_conf:
                    best_conf = conf; best_idx = si; best_reason = reason
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
    timings["leakage_sec"] = time.time() - t2
    stats["leak_calls"] = leak_calls

    timings["total_sec"] = sum(timings.values())

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
        "intent": {
            "items": intent_items,
            "buckets": intent_buckets
        },
        "timings": timings,
        "stats": stats,
    }
    return run

def save_run(run: Dict[str, Any], out_path: str) -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=2)
