# gsd/apply.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from pathlib import Path
import json

def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows

def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def _ensure_list(x):
    return x if isinstance(x, list) else ([] if x is None else [x])

def apply_autofix(run: Dict[str, Any], *, dataset_path: str, out_dataset_path: str, changelog_path: str) -> None:
    """
    - Merge duplicates: keep canonical, append member expected/accepted into canonical.accepted
    - Mark leakage items as open-book by setting context_url to the matched file (if empty)
    - DOES NOT auto-edit rubric issues; lists them in CHANGELOG for human action
    """
    src = Path(dataset_path)
    rows = _read_jsonl(src)
    by_id = {r.get("id"): r for r in rows}
    order = [r.get("id") for r in rows]

    removed_ids: List[str] = []
    merged_into: Dict[str, List[str]] = {}
    leakage_marked: List[Tuple[str, str]] = []  # (id, file)

    # 1) merge duplicates
    for cl in run.get("dup_clusters", []):
        canon_id = cl["canonical"]
        members = cl.get("members", [])
        if canon_id not in by_id:
            continue
        canon = by_id[canon_id]
        canon.setdefault("accepted", [])
        canon_acc = set(canon["accepted"])

        # Include canonical expected into accepted? Not necessary; keep as-is
        for mid in members:
            m = by_id.get(mid)
            if not m:
                continue
            # Move member expected + accepted into canonical.accepted
            mex = m.get("expected")
            if mex and mex not in canon_acc:
                canon["accepted"].append(mex); canon_acc.add(mex)
            for a in _ensure_list(m.get("accepted")):
                if a and a not in canon_acc:
                    canon["accepted"].append(a); canon_acc.add(a)
            # Remove member
            removed_ids.append(mid)
            merged_into.setdefault(canon_id, []).append(mid)
            by_id.pop(mid, None)

    # rebuild ordered list without removed
    new_rows: List[Dict[str, Any]] = []
    for i in order:
        if i not in by_id:
            continue
        new_rows.append(by_id[i])

    # 2) mark leakage as open-book (context_url)
    for hit in run.get("leakage", []):
        iid = hit.get("item_id")
        fpath = hit.get("file")
        if iid in by_id:
            it = by_id[iid]
            if not it.get("context_url"):
                it["context_url"] = fpath
                leakage_marked.append((iid, fpath))

    # 3) write dataset_v2
    _write_jsonl(Path(out_dataset_path), new_rows)

    # 4) changelog
    rub = run.get("rubric", {})
    err_count = rub.get("counts", {}).get("errors", 0)
    warn_count = rub.get("counts", {}).get("warnings", 0)

    lines: List[str] = []
    lines.append("# Golden-Set Doctor: Applied Fixes\n")
    lines.append(f"- Source dataset: `{dataset_path}`\n")
    lines.append(f"- Output dataset: `{out_dataset_path}`\n")

    if merged_into:
        lines.append("## Duplicate merges\n")
        for cid, mids in merged_into.items():
            mids_s = ", ".join(f"`{m}`" for m in mids)
            lines.append(f"- Kept `{cid}` as canonical; merged members: {mids_s}. Appended members' expected/accepted to canonical `accepted`.")
        lines.append("")

    if leakage_marked:
        lines.append("## Leakage marked as open-book\n")
        for iid, fp in leakage_marked:
            lines.append(f"- `{iid}`: set `context_url` to `{fp}`")
        lines.append("")

    if err_count or warn_count:
        lines.append("## Rubric issues (manual action suggested)\n")
        lines.append(f"- Errors: **{err_count}**, Warnings: **{warn_count}**\n")
        # list first few examples
        for it in rub.get("items", [])[:20]:
            iid = it.get("id", "")
            for iss in it.get("issues", []):
                lines.append(f"  - `{iid}` [{iss.get('severity')}:{iss.get('code')}]: {iss.get('reason')}  \n    Suggest: {iss.get('suggest','')}")
        lines.append("")

    Path(changelog_path).write_text("\n".join(lines), encoding="utf-8")
