#!/usr/bin/env python3
"""
Generate an HTML report with summary stats and inline SVG charts for
hybrid-extracted-instructions-grade{3..8}.csv.

No external dependencies.
"""

import csv
import glob
import json
import os
from collections import Counter, defaultdict
from typing import Dict, List


CONF_ORDER = ["Very Low", "Low", "Medium", "High", "Very High"]
CONF_COLORS = {
    "Very Low": "#d73027",
    "Low": "#fc8d59",
    "Medium": "#fee08b",
    "High": "#91bfdb",
    "Very High": "#4575b4",
}


def read_grade_file(path: str) -> Dict:
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    sims = [float(r.get("similarity_score", "0") or 0) for r in rows]
    conf = Counter(r.get("match_confidence", "") for r in rows)
    llm_calls = sum(1 for r in rows if (r.get("llm_explanation") or "").strip())
    avg = round(sum(sims) / len(sims), 3) if sims else 0.0
    # normalize confidence keys
    conf_norm = {k: conf.get(k, 0) for k in CONF_ORDER}
    return {
        "rows": len(rows),
        "avg": avg,
        "confidence": conf_norm,
        "llm_calls": llm_calls,
    }


def load_all_stats() -> Dict[str, Dict]:
    stats: Dict[str, Dict] = {}
    for path in sorted(glob.glob("hybrid-extracted-instructions-grade*.csv")):
        # get grade from filename
        base = os.path.basename(path)
        # expected pattern: hybrid-extracted-instructions-grade{N}.csv
        try:
            grade = base.split("grade")[-1].split(".")[0]
        except Exception:
            continue
        stats[grade] = read_grade_file(path)
    return stats


def svg_bar_chart(title: str, data: Dict[str, int], total: int, width: int = 640, height: int = 160) -> str:
    # simple horizontal bar chart by category (CONF_ORDER)
    padding = 10
    bar_h = (height - padding * 2) // len(CONF_ORDER)
    max_value = max(data.values()) if data else 1
    chart = [f'<svg width="{width}" height="{height}" role="img" aria-label="{title}">']
    chart.append(f'<rect width="100%" height="100%" fill="#ffffff"/>')
    chart.append(f'<text x="{padding}" y="{padding + 12}" font-family="sans-serif" font-size="12" fill="#333">{title}</text>')
    y = padding + 20
    for label in CONF_ORDER:
        value = data.get(label, 0)
        # bar length scaled to max_value (better for visual contrast)
        bar_w = int((width - 180) * (value / max_value)) if max_value > 0 else 0
        color = CONF_COLORS.get(label, "#999")
        chart.append(f'<rect x="150" y="{y}" width="{bar_w}" height="{bar_h - 6}" fill="{color}" rx="3" ry="3"/>')
        chart.append(f'<text x="10" y="{y + bar_h - 10}" font-family="sans-serif" font-size="12" fill="#333">{label}</text>')
        chart.append(f'<text x="{150 + bar_w + 6}" y="{y + bar_h - 10}" font-family="sans-serif" font-size="12" fill="#333">{value}</text>')
        y += bar_h
    chart.append('</svg>')
    return "\n".join(chart)


def generate_html(stats: Dict[str, Dict]) -> str:
    grades_sorted = sorted(stats.keys(), key=lambda g: int(g))
    # totals
    total_rows = sum(s["rows"] for s in stats.values())
    total_calls = sum(s["llm_calls"] for s in stats.values())
    avg_all = round(
        sum(s["avg"] * s["rows"] for s in stats.values()) / total_rows, 3
    ) if total_rows else 0.0
    total_conf = Counter()
    for s in stats.values():
        total_conf.update(s["confidence"]) 
    total_conf_norm = {k: total_conf.get(k, 0) for k in CONF_ORDER}

    # HTML
    parts: List[str] = []
    parts.append("<!doctype html>")
    parts.append("<meta charset=\"utf-8\">")
    parts.append("<title>Hybrid Matching Report (Grades 3–8)</title>")
    parts.append("<style>body{font-family:sans-serif;margin:24px;}h1{margin:0 0 8px}table{border-collapse:collapse;margin:12px 0;width:100%;}th,td{border:1px solid #ddd;padding:8px;font-size:14px}th{background:#f8f8f8;text-align:left}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px}.pill{display:inline-block;padding:2px 8px;border-radius:12px;background:#f0f0f0;margin-right:6px}code{background:#f7f7f7;padding:2px 4px;border-radius:4px}</style>")
    parts.append("<h1>Hybrid Matching Report (Grades 3–8)</h1>")
    parts.append(f"<p>Total rows: <b>{total_rows}</b> &nbsp; Avg similarity: <b>{avg_all}</b> &nbsp; LLM calls: <b>{total_calls}</b></p>")

    # Overall chart
    parts.append("<h2>Overall Confidence Distribution</h2>")
    parts.append(svg_bar_chart("All Grades", total_conf_norm, total_rows))

    # Per-grade table
    parts.append("<h2>Per-grade Summary</h2>")
    parts.append("<table>")
    parts.append("<tr><th>Grade</th><th>Rows</th><th>Avg Similarity</th><th>LLM Calls</th><th>Confidence (Very Low/Low/Medium/High/Very High)</th></tr>")
    for g in grades_sorted:
        s = stats[g]
        conf = s["confidence"]
        conf_str = f"{conf['Very Low']}/{conf['Low']}/{conf['Medium']}/{conf['High']}/{conf['Very High']}"
        parts.append(
            f"<tr><td>{g}</td><td>{s['rows']}</td><td>{s['avg']}</td><td>{s['llm_calls']}</td><td>{conf_str}</td></tr>"
        )
    parts.append("</table>")

    # Per-grade charts
    parts.append("<h2>Per-grade Confidence Charts</h2>")
    parts.append("<div class=\"grid\">")
    for g in grades_sorted:
        s = stats[g]
        parts.append("<div>")
        parts.append(f"<h3>Grade {g} <span class=\"pill\">rows: {s['rows']}</span> <span class=\"pill\">avg: {s['avg']}</span> <span class=\"pill\">LLM: {s['llm_calls']}</span></h3>")
        parts.append(svg_bar_chart(f"Grade {g}", s["confidence"], s["rows"]))
        parts.append("</div>")
    parts.append("</div>")

    parts.append("<p style=\"color:#777;margin-top:24px\">Generated by <code>generate_hybrid_report.py</code>.</p>")
    return "\n".join(parts)


def main():
    stats = load_all_stats()
    html = generate_html(stats)
    out_path = "hybrid_report.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report written to {out_path}")


if __name__ == "__main__":
    main()





