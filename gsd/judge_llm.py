# gsd/judge_llm.py
from __future__ import annotations
import json, hashlib
from pathlib import Path
from typing import Dict, Tuple, List, Optional
from tqdm import tqdm

try:
    from litellm import completion  # vendor-agnostic (OpenAI, Azure, etc.)
except Exception:
    completion = None

CACHE_PATH = Path(".run/llm_cache.jsonl")

def _hash_key(system: str, user: str, model: str, temperature: float) -> str:
    h = hashlib.sha256()
    h.update(f"{system}\n{user}\n{model}\n{temperature}".encode("utf-8"))
    return h.hexdigest()[:16]

def _cache_get(key: str) -> Optional[Dict]:
    if not CACHE_PATH.exists():
        return None
    with CACHE_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("key") == key:
                return rec.get("parsed")
    return None

def _cache_put(key: str, parsed: Dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "parsed": parsed}, ensure_ascii=False) + "\n")

def _call_llm(system: str, user: str, model: str, temperature: float = 0.0) -> Dict:
    if completion is None:
        raise RuntimeError("litellm is not installed. Run: pip install litellm")
    key = _hash_key(system, user, model, temperature)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    resp = completion(
        model=model, temperature=temperature,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}]
    )
    text = getattr(resp.choices[0].message, "content", str(resp))
    try:
        parsed = json.loads(text)
    except Exception:
        import re
        m = re.search(r"\{.*\}", text, re.S)
        parsed = json.loads(m.group(0)) if m else {"error": "parse_failed", "raw": text}
    _cache_put(key, parsed)
    return parsed

# ---------- DUPLICATE JUDGE ----------
DUP_SYSTEM = (
    "You are a precise evaluator for near-duplicate detection in user queries. "
    "Decide if two queries ask for the SAME underlying task/intent. "
    "If verbs differ in DIRECTION (e.g., create vs delete), they are NOT duplicates. "
    "Ignore superficial rewording. Respond ONLY as JSON: "
    "{\"duplicate\": true|false, \"confidence\": 0..1, \"reason\": \"<short>\"}"
)

def _dup_user(a: str, b: str) -> str:
    return f"Query A: {a}\nQuery B: {b}\nAre these the same underlying task?"

def judge_duplicate(q1: str, q2: str, model: str, temperature: float = 0.0) -> Tuple[bool, float, str]:
    out = _call_llm(DUP_SYSTEM, _dup_user(q1, q2), model, temperature)
    dup = bool(out.get("duplicate") is True)
    conf = float(out.get("confidence", 0))
    reason = str(out.get("reason", ""))
    return dup, conf, reason

def llm_cluster_duplicates(questions: List[str], model: str,
                           threshold: float = 0.6, temperature: float = 0.0,
                           progress: bool = True):
    """
    All-pairs clustering judged by the LLM. Returns (clusters, stats).
    stats={'pairs': total, 'accepted': edges_kept}
    """
    n = len(questions)
    parent = list(range(n)); rank = [0]*n
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

    total = n * (n - 1) // 2
    kept = 0
    bar = tqdm(total=total, desc="Duplicate pairs", unit="pair", leave=False, disable=not progress)
    for i in range(n):
        for j in range(i+1, n):
            dup, conf, _ = judge_duplicate(questions[i], questions[j], model, temperature)
            score = conf if dup else 0.0  # only count when derived TRUE (no inversions)
            if score >= threshold:
                union(i, j); kept += 1
            bar.update(1)
    bar.close()

    clusters: Dict[int, List[int]] = {}
    for i in range(n):
        r = find(i)
        clusters.setdefault(r, []).append(i)
    clusters = [sorted(v) for v in clusters.values() if len(v) >= 2]
    return clusters, {"pairs": total, "accepted": kept}

# ---------- LEAKAGE JUDGE ----------
LEAK_SYSTEM = (
    "You evaluate whether the EXPECTED ANSWER is effectively stated or directly derivable "
    "from the REFERENCE SENTENCE (treat as 'open-book'). "
    "Be conservative: paraphrases conveying the same fact count as derived. "
    "Respond ONLY as JSON: {\"derived\": true|false, \"confidence\": 0..1, \"reason\": \"<short>\"}"
)

def _leak_user(expected: str, snippet: str) -> str:
    return f"Expected answer:\n{expected}\n\nReference sentence:\n{snippet}\n\nIs the expected answer stated/derivable?"

def judge_leakage(expected: str, snippet: str, model: str, temperature: float = 0.0) -> Tuple[bool, float, str]:
    out = _call_llm(LEAK_SYSTEM, _leak_user(expected, snippet), model, temperature)
    derived = bool(out.get("derived") is True)
    conf = float(out.get("confidence", 0))
    reason = str(out.get("reason", ""))
    return derived, conf, reason
