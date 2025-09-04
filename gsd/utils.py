# gsd/utils.py
from __future__ import annotations
import json, re
from pathlib import Path
from typing import List, Dict, Any, Iterable

# ---------- JSONL ----------
def load_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items

def save_jsonl(items: Iterable[Dict[str, Any]], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

# ---------- Text helpers ----------
_ws = re.compile(r"\s+")
def normalize_text(s: str) -> str:
    return _ws.sub(" ", s.strip())

def item_input_text(item: Dict[str, Any]) -> str:
    return str(item.get("input") or item.get("query") or "")

def item_expected_text(item: Dict[str, Any]) -> str:
    return str(item.get("expected") or "")

# ---------- Reference docs → sentence index ----------
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}|^\s*[-*]\s+", re.MULTILINE)

def iter_doc_sentences(refs_dir: str | Path) -> List[Dict[str, str]]:
    """
    Scan refs_dir for .txt/.md files and return a list of sentence dicts:
      { 'file': 'path', 'text': 'sentence' }
    """
    out: List[Dict[str, str]] = []
    refs = Path(refs_dir)
    if not refs.exists():
        return out
    for fp in refs.rglob("*"):
        if not fp.is_file():
            continue
        if fp.suffix.lower() not in {".txt", ".md"}:
            continue
        try:
            raw = fp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        # Split into sentences/blocks; keep short bullets too
        parts = [p.strip() for p in _SENT_SPLIT.split(raw) if p and p.strip()]
        for sent in parts:
            out.append({"file": fp.as_posix(), "text": sent})
    return out
