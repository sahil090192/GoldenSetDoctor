# gsd/apply.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Set
from .utils import load_jsonl, save_jsonl

def _index_by_id(items: List[Dict[str, Any]]):
    idx = {}
    for i, it in enumerate(items):
        idx[it.get("id", f"it_{i}")] = i
    return idx

def _append_variant(canon: Dict[str, Any], variant_expected: str):
    if not variant_expected: return
    if "accepted" not in canon or not isinstance(canon["accepted"], list):
        canon["accepted"] = []
    if variant_expected != canon.get("expected") and variant_expected not in canon["accepted"]:
        canon["accepted"].append(variant_expected)

def apply_autofix(run: Dict[str, Any], dataset_path: str, out_dataset_path: str, changelog_path: str):
    items = load_jsonl(dataset_path)
    id2idx = _index_by_id(items)
    removed_ids: Set[str] = set()
    modified_ids: Set[str] = set()

    for cl in run.get("dup_clusters", []):
        canon_id = cl["canonical"]
        canon_idx = id2idx.get(canon_id)
        if canon_idx is None: continue
        canon_item = items[canon_idx]
        for mid in cl["members"]:
            m_idx = id2idx.get(mid)
            if m_idx is None or mid in removed_ids: continue
            m_item = items[m_idx]
            _append_variant(canon_item, m_item.get("expected",""))
            removed_ids.add(mid); modified_ids.add(canon_id)

    if removed_ids:
        items = [it for it in items if it.get("id") not in removed_ids]
        id2idx = _index_by_id(items)

    for leak in run.get("leakage", []):
        lid = leak["item_id"]; idx = id2idx.get(lid)
        if idx is None: continue
        it = items[idx]
        if "context_url" not in it:
            it["context_url"] = leak["file"]; modified_ids.add(lid)

    save_jsonl(items, out_dataset_path)

    added = 0; removed = len(removed_ids); modified = len(modified_ids)
    lines = [
        "## v2 (auto-fix)",
        f"- Removals (dup members): {removed}",
        f"- Modifications (variants/context): {modified}",
        f"- Additions: {added}", "", "### Details",
    ]
    if removed_ids: lines.append(f"- Removed IDs: {', '.join(sorted(removed_ids))}")
    if modified_ids: lines.append(f"- Modified IDs: {', '.join(sorted(modified_ids))}")
    Path(changelog_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
