# gsd/judge_llm.py
from __future__ import annotations
import json, hashlib, re
from pathlib import Path
from typing import Dict, Tuple, List, Optional
from tqdm import tqdm

try:
    from litellm import completion  # provider-agnostic (OpenAI, Azure, etc.)
except Exception:
    completion = None

CACHE_PATH = Path(".run/llm_cache.jsonl")

# -------------------- cache --------------------
def _hkey(system: str, user: str, model: str, temperature: float) -> str:
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

def _call(system: str, user: str, model: str, temperature: float = 0.0) -> Dict:
    if completion is None:
        raise RuntimeError("litellm is not installed. Run: pip install litellm")
    key = _hkey(system, user, model, temperature)
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
        m = re.search(r"\{.*\}", text, re.S)
        parsed = json.loads(m.group(0)) if m else {"error": "parse_failed", "raw": text}
    _cache_put(key, parsed)
    return parsed

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

# -------------------- duplicate judge --------------------
DUP_SYSTEM = (
    "You are a precise evaluator for near-duplicate detection in user queries. "
    "Two queries are duplicates ONLY if they ask for the SAME underlying task/slot about the same subject. "
    "If verbs or slots differ in DIRECTION (create vs delete, where vs when, who vs what), they are NOT duplicates. "
    "Respond ONLY as JSON: {\"duplicate\": true|false, \"confidence\": 0..1, \"reason\": \"<short>\"}."
)
def _dup_user(a: str, b: str) -> str:
    return f"Query A: {a}\nQuery B: {b}\nAre these the same underlying task?"

def judge_duplicate(q1: str, q2: str, model: str, temperature: float = 0.0) -> Tuple[bool, float, str]:
    out = _call(DUP_SYSTEM, _dup_user(q1, q2), model, temperature)
    dup = bool(out.get("duplicate") is True)
    conf = float(out.get("confidence", 0))
    reason = str(out.get("reason", ""))
    return dup, conf, reason

# -------------------- intent bucketing --------------------
INTENT_SYSTEM = (
    "Derive a compact INTENT KEY for a question so that any two questions sharing the same key "
    "ask for the SAME slot about the SAME subject.\n"
    "Return JSON:\n"
    "{"
    "  \"key\": \"topic|slot|scope\","
    "  \"topic\": \"<main subject/entity>\","
    "  \"slot\": \"<what is asked: who/where/when/date/venue/winner/definition/count/etc>\","
    "  \"scope\": \"<optional qualifier like AFC/NFC/year/team, else empty>\""
    "}\n"
    "Keys must be lowercase, hyphen-separated, and conservative."
)
def _intent_user(q: str) -> str:
    return f"Question: {q}\nEmit a conservative intent key."

def intent_key(q: str, model: str, temperature: float = 0.0) -> Tuple[str, Dict]:
    out = _call(INTENT_SYSTEM, _intent_user(q), model, temperature)
    key = out.get("key") or out.get("intent_key") or ""
    topic = out.get("topic",""); slot = out.get("slot",""); scope = out.get("scope","")
    if not key:
        parts = [f"topic={_slug(topic)}" if topic else "",
                 f"slot={_slug(slot)}" if slot else "",
                 f"scope={_slug(scope)}" if scope else ""]
        key = "|".join([p for p in parts if p])
    return key, {"topic": topic, "slot": slot, "scope": scope}

def intent_keys(questions: List[str], model: str, temperature: float = 0.0, progress: bool = True):
    keys: List[str] = []
    meta: List[Dict] = []
    bar = tqdm(total=len(questions), desc="Intent keys", unit="q", leave=False, disable=not progress)
    for q in questions:
        k, m = intent_key(q, model, temperature)
        keys.append(k or f"fallback|{_slug(q[:40])}")
        meta.append(m)
        bar.update(1)
    bar.close()
    return keys, meta

# -------------------- bucket clustering --------------------
BUCKET_CLUSTER_SYSTEM = (
    "You are given a small list of questions that ALREADY share the same intent key. "
    "Group items that are near-duplicates (ask for the same underlying task/slot). "
    "Return ONLY JSON: {\"clusters\": [[0,3,5], [1,2]]}. Use 0-based indices."
)
def _bucket_user(items: List[str]) -> str:
    numbered = "\n".join([f"{i}. {s}" for i, s in enumerate(items)])
    return f"Questions:\n{numbered}\n\nGroup near-duplicates and return JSON."

def bucket_cluster(items: List[str], model: str, temperature: float = 0.0) -> List[List[int]]:
    out = _call(BUCKET_CLUSTER_SYSTEM, _bucket_user(items), model, temperature)
    clusters = out.get("clusters")
    if not isinstance(clusters, list):
        return []
    valid: List[List[int]] = []
    for g in clusters:
        try:
            group = sorted({int(x) for x in g if isinstance(x, (int, float))})
        except Exception:
            continue
        if len(group) >= 2 and all(0 <= x < len(items) for x in group):
            valid.append(group)
    return valid

# -------------------- leakage judge (missing in your file) --------------------
LEAK_SYSTEM = (
    "You evaluate whether the EXPECTED ANSWER is effectively stated or directly derivable "
    "from the REFERENCE SENTENCE (treat as 'open-book'). "
    "Be conservative: paraphrases conveying the same fact count as derived. "
    "Respond ONLY as JSON: {\"derived\": true|false, \"confidence\": 0..1, \"reason\": \"<short>\"}"
)
def _leak_user(expected: str, snippet: str) -> str:
    return f"Expected answer:\n{expected}\n\nReference sentence:\n{snippet}\n\nIs the expected answer stated/derivable?"

def judge_leakage(expected: str, snippet: str, model: str, temperature: float = 0.0) -> Tuple[bool, float, str]:
    out = _call(LEAK_SYSTEM, _leak_user(expected, snippet), model, temperature)
    derived = bool(out.get("derived") is True)
    conf = float(out.get("confidence", 0))
    reason = str(out.get("reason", ""))
    return derived, conf, reason
