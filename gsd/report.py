# gsd/report.py
from __future__ import annotations
import html
from pathlib import Path
from typing import Dict, Any, List

STYLE = """
body{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Helvetica,Arial,sans-serif;margin:24px;}
h1{margin:0 0 8px 0;}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0 20px;}
.card{border:1px solid #e5e7eb;border-radius:12px;padding:12px 14px;min-width:160px;box-shadow:0 1px 2px rgba(0,0,0,.03);}
.card .k{font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:.04em;}
.card .v{font-size:20px;font-weight:600;margin-top:4px;}
table{border-collapse:collapse;width:100%;margin-top:8px;}
th,td{border:1px solid #e5e7eb;padding:8px 10px;text-align:left;vertical-align:top;}
th{background:#f9fafb;font-weight:600;}
code{background:#f3f4f6;border:1px solid #e5e7eb;padding:2px 4px;border-radius:6px;}
.small{color:#6b7280;font-size:12px;}
footer{margin-top:28px;color:#6b7280;font-size:12px;}
.section{margin-top:18px;}
"""

def render_html(run: Dict[str, Any]) -> str:
    c = run["counts"]
    dup_pct = (100.0 * c["dup_members"] / max(1, c["items"]))
    status = "Healthy ✅" if (c["dup_members"] == 0 and c["leakage"] == 0) else "Needs attention ⚠️"

    head = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Golden-Set Doctor Report</title>"
        f"<style>{STYLE}</style></head><body>"
    )
    body: List[str] = []
    body.append(f"<h1>Golden-Set Doctor Report</h1>")
    body.append(f"<div class='small'>Dataset: <code>{html.escape(run['dataset'])}</code></div>")

    body.append("<div class='cards'>")
    body.append(card("Status", status))
    body.append(card("Items", str(c["items"])))
    body.append(card("Dup clusters", str(c["dup_clusters"])))
    body.append(card("Dup members", f"{c['dup_members']} ({dup_pct:.1f}%)"))
    body.append(card("Leakage", str(c["leakage"])))
    body.append("</div>")

    # Intent buckets (grouped)
    intent = run.get("intent")
    if intent and intent.get("buckets"):
        body.append("<div class='section'><h2>Intent buckets</h2>")
        rows = ["<table><thead><tr><th>Intent key</th><th>Members</th></tr></thead><tbody>"]
        for b in intent["buckets"]:
            members = "<br>".join(
                f"<code>{html.escape(m['id'])}</code>: {html.escape(m['input'])}"
                for m in b.get("members", [])
            )
            rows.append(
                f"<tr><td><code>{html.escape(b['key'])}</code> &nbsp;<span class='small'>(n={b.get('size',0)})</span></td>"
                f"<td>{members or '-'}</td></tr>"
            )
        rows.append("</tbody></table>")
        body += rows
        body.append("</div>")

    # Per-item intents
    if intent and intent.get("items"):
        body.append("<div class='section'><h2>Per-item intent keys</h2>")
        rows = ["<table><thead><tr><th>ID</th><th>Input</th><th>Intent key</th><th>Topic</th><th>Slot</th><th>Scope</th></tr></thead><tbody>"]
        for item in intent["items"]:
            rows.append(
                "<tr>"
                f"<td><code>{html.escape(item['id'])}</code></td>"
                f"<td>{html.escape(item['input'])}</td>"
                f"<td><code>{html.escape(item.get('key',''))}</code></td>"
                f"<td>{html.escape(item.get('topic',''))}</td>"
                f"<td>{html.escape(item.get('slot',''))}</td>"
                f"<td>{html.escape(item.get('scope',''))}</td>"
                "</tr>"
            )
        rows.append("</tbody></table>")
        body += rows
        body.append("</div>")

    # Duplicates
    if run["dup_clusters"]:
        body.append("<div class='section'><h2>Near-duplicate clusters</h2>")
        rows = ["<table><thead><tr><th>Canonical ID</th><th>Canonical input</th><th>Members</th></tr></thead><tbody>"]
        for cl in run["dup_clusters"]:
            members = "<br>".join(
                f"<code>{html.escape(mid)}</code>: {html.escape(inp)}"
                for mid, inp in zip(cl["members"], cl["member_inputs"])
            )
            rows.append(
                f"<tr><td><code>{html.escape(cl['canonical'])}</code></td>"
                f"<td>{html.escape(cl['canonical_input'])}</td>"
                f"<td>{members or '-'}</td></tr>"
            )
        rows.append("</tbody></table>")
        body += rows
        body.append("</div>")

    # Leakage
    if run["leakage"]:
        body.append("<div class='section'><h2>Leakage matches</h2>")
        rows = ["<table><thead><tr><th>Item ID</th><th>File</th><th>Match score</th><th>Reason</th><th>Snippet</th></tr></thead><tbody>"]
        for hit in run["leakage"]:
            score = hit.get("score", 0.0)
            reason = hit.get("reason", "")
            rows.append(
                f"<tr><td><code>{html.escape(hit['item_id'])}</code></td>"
                f"<td><code>{html.escape(hit['file'])}</code></td>"
                f"<td>{float(score):.3f}</td>"
                f"<td>{html.escape(reason)}</td>"
                f"<td>{html.escape(hit['snippet'])}</td></tr>"
            )
        rows.append("</tbody></table>")
        body += rows
        body.append("</div>")

    body.append("<footer>Generated by Golden-Set Doctor · LLM-only v1</footer>")
    return head + "\n".join(body) + "</body></html>"

def card(k: str, v: str) -> str:
    return f"<div class='card'><div class='k'>{k}</div><div class='v'>{v}</div></div>"

def save_html(run: Dict[str, Any], out_html: str) -> None:
    Path(out_html).write_text(render_html(run), encoding="utf-8")
