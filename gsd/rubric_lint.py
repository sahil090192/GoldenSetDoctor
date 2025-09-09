# gsd/rubric_lint.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
import time, re

try:
    # Reuse the cached LLM call from judge_llm for determinism & cost
    from .judge_llm import _call as llm_call
except Exception:
    llm_call = None  # LLM optional

# ---------- simple helpers ----------

_WORD_RE = re.compile(r"[A-Za-z0-9]+")

def _word_count(s: str) -> int:
    return len(_WORD_RE.findall(s or ""))

def _has_placeholder(s: str) -> bool:
    s = (s or "").lower()
    return any(tok in s for tok in ["<", "…", "...", "tbd", "todo", "lorem ipsum", "[insert", "{", "}", "___"])

def _has_multi_intent(text: str) -> bool:
    # crude signals: 'and', 'also', 'as well as' joining actions; presence of multiple imperatives
    t = (text or "").lower()
    return (" and " in t or " as well as " in t) and any(x in t for x in ["create", "add", "format", "configure", "enable", "insert", "export"])

def _looks_subjective(q: str) -> bool:
    ql = (q or "").lower()
    return any(w in ql for w in ["best", "recommend", "should i", "can you explain", "why is", "pros and cons"])

def _has_time_words(q: str) -> bool:
    ql = (q or "").lower()
    return any(w in ql for w in ["latest", "currently", "right now", "as of"])

def _ambiguous_pronouns(q: str) -> bool:
    ql = (q or "").lower()
    return any(f" {w} " in f" {ql} " for w in ["it", "this", "that", "there", "they"])

# ---------- LLM judge ----------

RUBRIC_SYSTEM = (
    "You are a strict rubric auditor for LLM evaluation items.\n"
    "Given a QUESTION and its EXPECTED ANSWER, decide:\n"
    "- ambiguous: true if the question lacks necessary scope (product/app/version) or is vague\n"
    "- multi_intent: true if it asks more than one actionable task\n"
    "- gradeable: true if the expected answer is concrete enough to evaluate (objective criteria)\n"
    "Return ONLY JSON:\n"
    "{"
    "  \"ambiguous\": true|false,"
    "  \"multi_intent\": true|false,"
    "  \"gradeable\": true|false,"
    "  \"reasons\": [\"short reason\", ...],"
    "  \"suggest\": \"how to rewrite or clarify\"\n"
    "}"
)

def _rubric_user(q: str, exp: str) -> str:
    return f"QUESTION:\n{q}\n\nEXPECTED:\n{exp or ''}\n"

def _llm_assess(q: str, exp: str, model: str, temperature: float = 0.0) -> Dict[str, Any]:
    if llm_call is None:
        # LLM unavailable; default to safe 'unknown'
        return {"ambiguous": False, "multi_intent": False, "gradeable": True, "reasons": ["llm_unavailable"], "suggest": ""}
    out = llm_call(RUBRIC_SYSTEM, _rubric_user(q, exp), model=model, temperature=temperature)
    # be robust to model format
    return {
        "ambiguous": bool(out.get("ambiguous", False)),
        "multi_intent": bool(out.get("multi_intent", False)),
        "gradeable": bool(out.get("gradeable", True)),
        "reasons": out.get("reasons", []),
        "suggest": out.get("suggest", ""),
    }

# ---------- lint engine ----------

def lint_item(item: Dict[str, Any],
              *,
              short_min_words: int = 6,
              long_max_words: int = 100,
              use_llm: bool = True,
              model: str = "",
              temperature: float = 0.0) -> List[Dict[str, Any]]:
    """
    Returns a list of issue dicts:
      {severity: 'error'|'warn'|'info', code: '...', reason: '...', suggest: '...'}
    """
    issues: List[Dict[str, Any]] = []
    q = (item.get("input") or "").strip()
    exp = (item.get("expected") or "").strip()

    # Presence
    if not exp:
        issues.append({"severity": "error", "code": "missing_expected",
                       "reason": "Expected answer is missing or empty.", "suggest": "Add a concise, objective expected answer."})
        # If missing expected, we still continue (LLM may also point out ambiguity)

    # Size heuristics
    wc = _word_count(exp)
    if exp and wc < short_min_words:
        issues.append({"severity": "warn", "code": "too_short",
                       "reason": f"Expected answer is very short ({wc} words).",
                       "suggest": "Add minimal steps or criteria to make it gradeable."})
    if exp and wc > long_max_words:
        issues.append({"severity": "warn", "code": "too_long",
                       "reason": f"Expected answer is long ({wc} words).",
                       "suggest": "Condense to essential, testable steps (80–120 words max)."})

    # Placeholders
    if exp and _has_placeholder(exp):
        issues.append({"severity": "warn", "code": "placeholder_expected",
                       "reason": "Expected contains placeholders or ellipses.",
                       "suggest": "Replace placeholders with concrete steps/values."})

    # Multi-intent signals (from input)
    if _has_multi_intent(q):
        issues.append({"severity": "error", "code": "multi_intent_signals",
                       "reason": "Question likely asks for multiple actions.",
                       "suggest": "Split into separate, single-task items."})

    # Ambiguity and subjectivity (quick lexical)
    if _looks_subjective(q):
        issues.append({"severity": "warn", "code": "subjective_query",
                       "reason": "Subjective/open-ended phrasing.",
                       "suggest": "Rewrite to a concrete, factual task with objective criteria."})
    if _has_time_words(q):
        issues.append({"severity": "warn", "code": "time_sensitive",
                       "reason": "Time-relative language ('latest', 'currently').",
                       "suggest": "Pin to a time or version (e.g., 'as of 2024-04')."})
    if _ambiguous_pronouns(q) and len(q.split()) <= 8:
        issues.append({"severity": "warn", "code": "ambiguous_pronouns",
                       "reason": "Very short question with vague pronouns.",
                       "suggest": "Name the product/scope explicitly."})

    # Optional LLM assessment
    if use_llm and model:
        ass = _llm_assess(q, exp, model=model, temperature=temperature)
        if ass.get("multi_intent", False):
            issues.append({"severity": "error", "code": "multi_intent_llm",
                           "reason": "LLM judged this as multi-intent.", "suggest": ass.get("suggest", "")})
        if ass.get("ambiguous", False):
            issues.append({"severity": "warn", "code": "ambiguous_llm",
                           "reason": "LLM flagged missing scope or vague phrasing.", "suggest": ass.get("suggest", "")})
        if not ass.get("gradeable", True):
            issues.append({"severity": "error", "code": "not_gradeable",
                           "reason": "LLM judged the expected answer not sufficiently objective to grade.",
                           "suggest": ass.get("suggest", "")})

    return issues

def lint_dataset(items: List[Dict[str, Any]],
                 *,
                 short_min_words: int = 6,
                 long_max_words: int = 100,
                 use_llm: bool = True,
                 model: str = "",
                 temperature: float = 0.0) -> Tuple[Dict[str, Any], float]:
    """
    Returns (rubric_result, elapsed_sec)
    rubric_result = {
      "counts": {"errors": int, "warnings": int, "infos": int},
      "items": [{"id":..., "input":..., "issues":[...]}]
    }
    """
    t0 = time.time()
    out_items: List[Dict[str, Any]] = []
    e = w = i = 0
    for it in items:
        issues = lint_item(
            it, short_min_words=short_min_words, long_max_words=long_max_words,
            use_llm=use_llm, model=model, temperature=temperature
        )
        if issues:
            out_items.append({"id": it.get("id"), "input": it.get("input", ""), "issues": issues})
            for iss in issues:
                if iss["severity"] == "error": e += 1
                elif iss["severity"] == "warn": w += 1
                else: i += 1
    res = {
        "counts": {"errors": e, "warnings": w, "infos": i},
        "items": out_items
    }
    return res, (time.time() - t0)
