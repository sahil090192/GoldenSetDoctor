# gsd/report.py
from __future__ import annotations
import html
from pathlib import Path
from typing import Dict, Any, List

DARK_STYLE = """
:root{
  --bg:#0b0f14; --panel:#11161d; --muted:#8892a6; --text:#e6ebf2;
  --border:#1f2a37; --accent:#1de9b6; --accent2:#7dd3fc; --warn:#facc15; --err:#f87171; --ok:#34d399;
  --code:#0f172a; --chip:#0d1320;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Ubuntu,Cantarell,Noto Sans,Helvetica,Arial,"Apple Color Emoji","Segoe UI Emoji";}
h1,h2,h3{font-weight:700;letter-spacing:.2px}
h1{font-size:34px;margin:16px 0 8px}
h2{font-size:20px;margin:18px 0 8px}
.small{color:var(--muted);font-size:12px}
.container{max-width:1100px;margin:24px auto;padding:0 16px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin:14px 0 18px}
.card{background:linear-gradient(180deg,rgba(255,255,255,.02),rgba(255,255,255,.01));border:1px solid var(--border);border-radius:14px;padding:12px 14px;min-width:160px;box-shadow:0 6px 20px rgba(0,0,0,.25)}
.card .k{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.card .v{font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;font-size:20px;font-weight:700;margin-top:4px}
.badge{background:var(--chip);border:1px solid var(--border);border-radius:999px;padding:2px 8px;color:var(--muted);display:inline-block;font-size:12px}
table{border-collapse:collapse;width:100%;margin-top:8px;background:var(--panel);border:1px solid var(--border);border-radius:12px;overflow:hidden}
th,td{border-top:1px solid var(--border);padding:10px 12px;text-align:left;vertical-align:top}
th{background:rgba(255,255,255,.02);font-weight:600;color:var(--muted)}
code{background:var(--code);border:1px solid var(--border);padding:2px 6px;border-radius:8px;color:#cfe6ff}
.section{margin:18px 0}
footer{margin:28px 0 40px;color:var(--muted);font-size:12px}
.issue-err{background:rgba(248,113,113,.12);border:1px solid rgba(248,113,113,.4);color:#fecaca;padding:2px 8px;border-radius:999px;font-size:12px}
.issue-warn{background:rgba(250,204,21,.12);border:1px solid rgba(250,204,21,.4);color:#fde68a;padding:2px 8px;border-radius:999px;font-size:12px}
.kpi-ok{color:var(--ok)} .kpi-warn{color:var(--warn)} .kpi-err{color:var(--err)}
.more{background:transparent;border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:10px;cursor:pointer}
.more:hover{border-color:var(--accent)}
hr.sep{border:none;border-top:1px dashed var(--border);margin:18px 0}
"""

JS = """
<script>
function toggleRows(tblId, btnId){
  const tbl = document.getElementById(tblId);
  const btn = document.getElementById(btnId);
  if(!tbl) return;
  const rows = tbl.querySelectorAll('tbody tr[data-extra="1"]');
  if(rows.length===0) return;
  const hidden = rows[0].style.display === 'none';
  rows.forEach(r => r.style.display = hidden ? '' : 'none');
  if(btn) btn.innerText = hidden ? 'Show less' : 'Show more';
}
</script>
"""

def render_html(run: Dict[str, Any]) -> str:
    c = run["counts"]
    dup_pct = (100.0 * c["dup_members"] / max(1, c["items"]))
    status_ok = (c["dup_members"] == 0 and c["leakage"] == 0 and c.get("rubric_errors",0) == 0)
    status = "Healthy ✅" if status_ok else "Needs attention ⚠️"

    head = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'/>"
        "<title>Golden-Set Doctor Report</title>"
        f"<style>{DARK_STYLE}</style>{JS}</head><body><div class='container'>"
    )
    body: List[str] = []
    body.append("<h1>Golden-Set Doctor Report</h1>")
    body.append(f"<div class='small'>Dataset: <code>{html.escape(run['dataset'])}</code></div>")

    # KPI cards (Duplicate wording)
    body.append("<div class='cards'>")
    body.append(card("Status", status))
    body.append(card("Items", str(c["items"])))
    body.append(card("Duplicate clusters", str(c["dup_clusters"])))
    body.append(card("Duplicate members", f"{c['dup_members']} ({dup_pct:.1f}%)"))
    body.append(card("Leakage", str(c["leakage"])))
    body.append(card("Rubric errors", str(c.get("rubric_errors", 0))))
    body.append(card("Rubric warnings", str(c.get("rubric_warnings", 0))))
    body.append("</div>")

    # Top sections first: duplicates, leakage, rubric
    if run["dup_clusters"]:
        body.append(section_near_duplicates(run["dup_clusters"]))
    if run["leakage"]:
        body.append(section_leakage(run["leakage"]))
    rub = run.get("rubric", {})
    if rub and rub.get("items"):
        body.append(section_rubric(rub))

    body.append("<hr class='sep'/>")

    # Collapsible: Intent buckets
    intent = run.get("intent")
    if intent and intent.get("buckets"):
        body.append(section_buckets(intent["buckets"], top_n=5))
    # Collapsible: Per-item intent keys
    if intent and intent.get("items"):
        body.append(section_intent_items(intent["items"], top_n=5))

    body.append("<footer>Generated by Golden-Set Doctor · LLM-only v1</footer>")
    return head + "\n".join(body) + "</div></body></html>"

def card(k: str, v: str) -> str:
    return f"<div class='card'><div class='k'>{html.escape(k)}</div><div class='v'>{html.escape(v)}</div></div>"

def section_near_duplicates(dup_clusters: List[Dict[str, Any]]) -> str:
    rows = [
        "<div class='section'><h2>Near-duplicate clusters</h2>",
        "<table><thead><tr><th>Canonical ID</th><th>Canonical input</th><th>Members</th></tr></thead><tbody>"
    ]
    for cl in dup_clusters:
        members = "<br>".join(
            f"<code>{html.escape(mid)}</code>: {html.escape(inp)}"
            for mid, inp in zip(cl["members"], cl["member_inputs"])
        ) or "-"
        rows.append(
            f"<tr><td><code>{html.escape(cl['canonical'])}</code></td>"
            f"<td>{html.escape(cl['canonical_input'])}</td>"
            f"<td>{members}</td></tr>"
        )
    rows.append("</tbody></table></div>")
    return "\n".join(rows)

def section_leakage(leaks: List[Dict[str, Any]]) -> str:
    rows = [
        "<div class='section'><h2>Leakage matches</h2>",
        "<table><thead><tr><th>Item ID</th><th>File</th><th>Match score</th><th>Reason</th><th>Snippet</th></tr></thead><tbody>"
    ]
    for hit in leaks:
        score = float(hit.get("score", 0.0))
        rows.append(
            f"<tr><td><code>{html.escape(hit['item_id'])}</code></td>"
            f"<td><code>{html.escape(hit['file'])}</code></td>"
            f"<td class='{'kpi-ok' if score>=0.9 else ''}'>{score:.3f}</td>"
            f"<td>{html.escape(hit.get('reason',''))}</td>"
            f"<td>{html.escape(hit.get('snippet',''))}</td></tr>"
        )
    rows.append("</tbody></table></div>")
    return "\n".join(rows)

def section_rubric(rub: Dict[str, Any]) -> str:
    rows = [
        "<div class='section'><h2>Rubric issues</h2>",
        "<table><thead><tr><th>ID</th><th>Input</th><th>Severity</th><th>Code</th><th>Reason</th><th>Suggested fix</th></tr></thead><tbody>"
    ]
    for it in rub.get("items", []):
        rid = it.get("id", "")
        rin = it.get("input", "")
        for iss in it.get("issues", []):
            sev = iss.get("severity", "info")
            badge = (
                "<span class='issue-err'>error</span>" if sev == "error"
                else "<span class='issue-warn'>warn</span>" if sev == "warn"
                else "info"
            )
            rows.append(
                f"<tr><td><code>{html.escape(str(rid))}</code></td>"
                f"<td>{html.escape(rin)}</td>"
                f"<td>{badge}</td>"
                f"<td><code>{html.escape(iss.get('code',''))}</code></td>"
                f"<td>{html.escape(iss.get('reason',''))}</td>"
                f"<td>{html.escape(iss.get('suggest',''))}</td></tr>"
            )
    rows.append("</tbody></table></div>")
    return "\n".join(rows)

def _collapsible_table(row_cells: List[str], table_id: str, btn_id: str, header_html: str, top_n: int) -> str:
    # row_cells: list of "<td>...</td><td>...</td>..." (one row worth of tds)
    body_rows: List[str] = []
    for i, cells in enumerate(row_cells):
        if i < top_n:
            body_rows.append(f"<tr>{cells}</tr>")
        else:
            body_rows.append(f"<tr data-extra='1' style='display:none'>{cells}</tr>")
    btn = f"<div style='margin-top:10px'><button id='{btn_id}' class='more' onclick=\"toggleRows('{table_id}','{btn_id}')\">Show more</button></div>"
    return f"<table id='{table_id}'>{header_html}<tbody>{''.join(body_rows)}</tbody></table>{btn}"

def section_buckets(buckets: List[Dict[str, Any]], top_n: int = 5) -> str:
    rowhtml: List[str] = []
    for b in buckets:
        members = "<br>".join(
            f"<code>{html.escape(m['id'])}</code>: {html.escape(m['input'])}"
            for m in b.get("members", [])
        )
        rowhtml.append(
            f"<td><code>{html.escape(b['key'])}</code> <span class='badge'>(n={b.get('size',0)})</span></td>"
            f"<td>{members or '-'}</td>"
        )
    header = "<thead><tr><th>Intent key</th><th>Members</th></tr></thead>"
    tbl = _collapsible_table(rowhtml, table_id="tblBuckets", btn_id="btnBuckets", header_html=header, top_n=top_n)
    return f"<div class='section'><h2>Intent buckets <span class='small'>(top {top_n} shown)</span></h2>{tbl}</div>"

def section_intent_items(items: List[Dict[str, Any]], top_n: int = 5) -> str:
    rowhtml: List[str] = []
    for it in items:
        trip = " | ".join([p for p in [it.get('topic',''), it.get('slot',''), it.get('scope','')] if p])
        rowhtml.append(
            f"<td><code>{html.escape(it['id'])}</code>: {html.escape(it['input'])}</td>"
            f"<td><code>{html.escape(it.get('key',''))}</code></td>"
            f"<td>{html.escape(trip)}</td>"
        )
    header = "<thead><tr><th>Item</th><th>Intent key</th><th>Topic | Slot | Scope</th></tr></thead>"
    tbl = _collapsible_table(rowhtml, table_id="tblIntent", btn_id="btnIntent", header_html=header, top_n=top_n)
    return f"<div class='section'><h2>Per-item intent keys <span class='small'>(top {top_n} shown)</span></h2>{tbl}</div>"

def save_html(run: Dict[str, Any], out_html: str) -> None:
    Path(out_html).write_text(render_html(run), encoding="utf-8")
