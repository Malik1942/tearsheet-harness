"""Post-step for the gate run: integrity checks and the run report (sections A-E of 05_gate_run_prompt.md).

    .venv/bin/python scripts/gate_report.py [YYYY-MM-DD]

Reads out/<stem>/spark_vision.json, ledger.csv, fixtures/gate_notes.md and fixtures/gate_notes.sha256.
Writes docs/GATE_RUN_<date>.md, copies overlays to docs/overlays/<stem>.png and saves unparsed raw text
to runs/<timestamp>/<stem>.raw.txt. Never calls the API and never edits model output.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT, DOCS, FIX = ROOT / "out", ROOT / "docs", ROOT / "fixtures"
LA = ZoneInfo("America/Los_Angeles")
ORDER = ["_smoke", "g1", "g2", "g3", "p1", "p2", "p3", "p4", "p5", "p6", "p7"]
ROLES = {"_smoke": "smoke", "g1": "gate", "g2": "gate", "g3": "gate", **{f"p{i}": "probe" for i in range(1, 8)}}
ENUM = {"type_scale_ratio", "hierarchy_mode", "density", "grouping", "rhythm", "alignment_edge",
        "image_text_dominance", "accent_placement", "accent_coverage", "palette_hue_count", "none"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(stem: str) -> dict | None:
    p = OUT / stem / "spark_vision.json"
    return json.loads(p.read_text()) if p.exists() else None


def integrity(b: dict) -> dict:
    m_ids = {m.get("id") for m in b.get("measurements", [])}
    h_ids = {h.get("id") for h in b.get("hypotheses", [])}
    return {
        "dangling_rests_on": [(h.get("id"), i) for h in b.get("hypotheses", []) for i in h.get("rests_on", []) if i not in m_ids],
        "dangling_region_ids": [(r.get("label"), i) for r in b.get("regions", []) for i in r.get("measurement_ids", []) if i not in m_ids],
        "dangling_source_hypothesis": [r.get("source_hypothesis") for r in b.get("transferable_relations", []) if r.get("source_hypothesis") not in h_ids],
        "parameter_outside_enum": [r.get("parameter") for r in b.get("transferable_relations", []) if r.get("parameter") not in ENUM],
        "none_count": sum(1 for r in b.get("transferable_relations", []) if r.get("parameter") == "none"),
    }


def ledger_rows() -> list[dict]:
    p = ROOT / "ledger.csv"
    return list(csv.DictReader(p.open(newline=""))) if p.exists() else []


def fmt_list(items) -> str:
    return "none" if not items else "; ".join(str(i) for i in items)


def main(argv: list[str]) -> None:
    now = datetime.now(LA)
    date = argv[0] if argv else now.strftime("%Y-%m-%d")
    run_dir = ROOT / "runs" / now.strftime("%Y%m%dT%H%M%S")
    (DOCS / "overlays").mkdir(parents=True, exist_ok=True)

    # A. config and integrity of the seal
    notes_path, sha_path = FIX / "gate_notes.md", FIX / "gate_notes.sha256"
    notes = notes_path.read_text()
    sealed_sha = sha_path.read_text().split()[0] if sha_path.exists() else ""
    seal_ok = sealed_sha and sealed_sha == sha256(notes_path)
    seal_line = "MATCH" if seal_ok else "SEALED NOTES CHANGED (run invalid)"
    sealed = {k: v for k, v in (l.split(": ", 1) for l in notes.splitlines() if ": " in l and not l.startswith("|"))}
    statements = {m.group(1): m.group(2).strip() for m in re.finditer(r"^\| (g[123]\.jpg) \| (.*?) \| .*\|$", notes, re.M)}

    reports = {s: load(s) for s in ORDER}
    efforts = sorted({r["effort"] for r in reports.values() if r})
    models = sorted({r["model"] for r in reports.values() if r})
    lines = [f"# Gate run {date}", "", f"Seal check: **{seal_line}**", "",
             "## A. Config and integrity", "",
             f"- Model id: {', '.join(models) or 'no calls found'}",
             f"- Effort actually used: {', '.join(efforts) or 'n/a'} (sealed: {sealed.get('Judged effort', '?')})",
             f"- Prompt sha256 now: `{sha256(FIX / 'prompts' / 'extract_brick.md')}` (sealed: `{sealed.get('Prompt sha256', '?')}`)",
             f"- Schema sha256 now: `{sha256(FIX / 'schemas' / 'brick.json')}` (sealed: `{sealed.get('Schema sha256', '?')}`)",
             f"- gate_notes.sha256: {seal_line}", ""]

    # B. per-call table
    lines += ["## B. Per-call table", "",
              "| Image | Role | Status | Latency ms | In tok | Out tok (reasoning) | $ | Schema valid | Meas | Hyp | Rel | Rel none | Dangling rests_on | Dangling region ids | Dangling source_hypothesis |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    integ = {}
    for stem in ORDER:
        r = reports[stem]
        if not r:
            lines.append(f"| {stem} | {ROLES[stem]} | not run | | | | | | | | | | | | |")
            continue
        call, usage = r.get("call", {}), r.get("call", {}).get("usage", {})
        valid = r.get("status") == "completed" and "result" in r
        b = r.get("result") or {}
        it = integ[stem] = integrity(b) if valid else None
        if not valid and r.get("raw_text") is not None:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / f"{stem}.raw.txt").write_text(r.get("raw_text", ""))
        ov = OUT / stem / "spark_overlay.png"
        if ov.exists():
            shutil.copy(ov, DOCS / "overlays" / f"{stem}.png")
        lines.append("| {} | {} | {} | {:.0f} | {} | {} ({}) | {:.4f} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            stem, ROLES[stem], r.get("status", "?"), call.get("latency_ms", 0), usage.get("input_tokens", 0),
            usage.get("output_tokens", 0), usage.get("reasoning_tokens", 0), call.get("cost_usd", 0),
            "yes" if valid else "NO (unparsed)",
            len(b.get("measurements", [])), len(b.get("hypotheses", [])), len(b.get("transferable_relations", [])),
            it["none_count"] if it else "", len(it["dangling_rests_on"]) if it else "",
            len(it["dangling_region_ids"]) if it else "", len(it["dangling_source_hypothesis"]) if it else ""))
    lines.append("")

    # C. gate side-by-side, verbatim, no judgment
    lines += ["## C. Gate side-by-side (g1-g3). Hit or miss is Malik's call against the sealed notes.", ""]
    for stem in ["g1", "g2", "g3"]:
        r = reports[stem]
        lines += [f"### {stem}.jpg", "", f"**Sealed statement:** {statements.get(stem + '.jpg', '(not found in gate_notes.md)')}", ""]
        if not r or "result" not in r:
            lines += [f"Model output: {'not run' if not r else 'unparsed (status ' + str(r.get('status')) + ')'}", ""]
            continue
        b, it = r["result"], integ.get(stem) or integrity(r["result"])
        lines.append("**Measurements (verbatim):**")
        for m in b.get("measurements", []):
            lines.append(f"- `{m.get('id')}` {m.get('statement')} | value: {m.get('value')} | how: {m.get('how_measured')}")
        lines += ["", "**Transferable relations (verbatim):**"]
        for rel in b.get("transferable_relations", []):
            lines.append(f"- rule: {rel.get('rule')} | parameter: `{rel.get('parameter')}` | target: {rel.get('target')} | source_hypothesis: `{rel.get('source_hypothesis')}`")
        lines += ["", "**Hypotheses:**"]
        m_ids = {m.get("id") for m in b.get("measurements", [])}
        for h in b.get("hypotheses", []):
            flags = [i for i in h.get("rests_on", []) if i not in m_ids]
            lines.append(f"- `{h.get('id')}` (confidence {h.get('confidence')}) {h.get('statement')} | rests_on: {', '.join(h.get('rests_on', [])) or 'EMPTY'}"
                         + (f" | DANGLING: {', '.join(flags)}" if flags else ""))
        lines += ["", f"**fragile_if_changed:** {b.get('fragile_if_changed')}", "",
                  f"Integrity: dangling rests_on {fmt_list(it['dangling_rests_on'])}; dangling region ids {fmt_list(it['dangling_region_ids'])}; "
                  f"dangling source_hypothesis {fmt_list(it['dangling_source_hypothesis'])}; parameters outside enum {fmt_list(it['parameter_outside_enum'])}",
                  f"Overlay: docs/overlays/{stem}.png", ""]

    # D. probe table (the measurement-led / adjective-led call is filled in by hand)
    lines += ["## D. Probe table (p1-p7)", "", "| Image | Dominant relation (model's words) | Parameters mapped | Dangling support | Measurement-led or adjective-led |", "|---|---|---|---|---|"]
    for stem in [f"p{i}" for i in range(1, 8)]:
        r = reports[stem]
        if not r or "result" not in r:
            lines.append(f"| {stem} | {'not run' if not r else 'unparsed'} | | | |")
            continue
        b, it = r["result"], integ.get(stem) or integrity(r["result"])
        rels = b.get("transferable_relations", [])
        dom = rels[0].get("rule") if rels else "(no relation)"
        params = ", ".join(f"`{x.get('parameter')}`" for x in rels) or "none"
        dangling = len(it["dangling_rests_on"]) + len(it["dangling_region_ids"]) + len(it["dangling_source_hypothesis"])
        lines.append(f"| {stem} | {dom} | {params} | {dangling} | ___ |")
    lines.append("")

    # E. spend
    rows = ledger_rows()
    today = [x for x in rows if x.get("timestamp", "").startswith(date)]
    spend = lambda xs: sum(float(x.get("est_cost_usd") or 0) for x in xs)
    lines += ["## E. Spend", "", f"- Today ({date}): {len(today)} calls, ${spend(today):.4f}",
              f"- Since the harness was built: {len(rows)} calls, ${spend(rows):.4f} of $150", ""]

    out = DOCS / f"GATE_RUN_{date}.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out}; seal {seal_line}; overlays in docs/overlays/; raw text in {run_dir if run_dir.exists() else '(none needed)'}")


if __name__ == "__main__":
    main(sys.argv[1:])
