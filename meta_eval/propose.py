"""Proposal regression (PRD 10.2): one Muse Spark TEXT call per intent against the sample library.

    python -m meta_eval.propose --intent "a one-line menu for a bakery" [--dry-run]

The model sees the intent and each brick's rules (id, rule text, parameter), never a photo, a measurement, a hypothesis
or the sealed notes. Same prompt, schema, effort and request shape as the product's /api/propose; a pick whose quoted
rule is not one of that brick's rules, character for character, is dropped and reported, never repaired.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from . import costs
from .client import OUT, ROOT, ApiError, Client, output_text

SCRIPT = "propose"
MODEL = "muse-spark-1.3"
EFFORT = "low"
MAX_OUT = 4000
PROMPT_FILE = ROOT / "fixtures" / "prompts" / "propose.md"
SCHEMA_FILE = ROOT / "fixtures" / "schemas" / "propose.json"
LIBRARY_DIR = ROOT.parent / "bricks" / "src" / "fixtures" / "samples"
MAX_INTENT_CHARS = 300


def load_library(directory: Path) -> list[dict[str, Any]]:
    """What the product sends (proposeClient.libraryFor): ready bricks, not superseded, at most three rules each."""
    library = []
    for path in sorted(directory.glob("*.json")):
        brick = json.loads(path.read_text())
        if brick.get("status", "ready") != "ready" or brick.get("superseded_by"):
            continue
        rules = [{"rule": r["rule"], "parameter": r["parameter"]} for r in brick.get("relations", [])[:3]]
        if rules:
            library.append({"brick_id": brick["id"], "rules": rules})
    return library


def render_prompt(template: str, intent: str, library: list[dict[str, Any]]) -> str:
    # Same two substitutions as the product (propose.ts renderPrompt); JSON.stringify(x, null, 1) == json.dumps(indent=1).
    return template.replace("{{INTENT}}", intent.replace('"', "”")).replace(
        "{{LIBRARY}}", json.dumps(library, indent=1, ensure_ascii=False))


def build_request(prompt: str, schema: dict[str, Any], effort: str, max_output_tokens: int) -> dict[str, Any]:
    return {
        "model": MODEL,
        "input": [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "text": {"format": {"type": "json_schema", "name": schema.get("title", "ProposeResult"), "schema": schema}},
        "reasoning": {"effort": effort},
        "max_output_tokens": max_output_tokens,
        "store": False,
    }


def validate_picks(raw: list[dict[str, Any]], library: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    by_id = {b["brick_id"]: b for b in library}
    picks: list[dict[str, str]] = []
    dropped: list[dict[str, str]] = []
    for p in raw:
        brick = by_id.get(p.get("brick_id"))
        if brick is None:
            dropped.append({"brick_id": str(p.get("brick_id")), "reason": "not a brick in the library"})
            continue
        if any(x["brick_id"] == p["brick_id"] for x in picks):
            dropped.append({"brick_id": p["brick_id"], "reason": "picked twice"})
            continue
        quote = str(p.get("quoted_rule", "")).strip()
        if not any(r["rule"].strip() == quote for r in brick["rules"]):
            dropped.append({"brick_id": p["brick_id"], "reason": "the reason does not quote one of its rules verbatim"})
            continue
        if len(picks) >= 3:
            dropped.append({"brick_id": p["brick_id"], "reason": "more than three picks"})
            continue
        picks.append({"brick_id": p["brick_id"], "quoted_rule": quote, "why": str(p.get("why", "")).strip()})
    return picks, dropped


def expected_from_notes(notes: Path, intent: str, known_ids: set[str]) -> tuple[list[str], list[str]] | None:
    """Read the sealed notes AFTER the call, only to score it: the ids on the `Picks:` line under this intent's heading,
    and the ids named on its `Not:` line (a pick of one of those counts as a miss)."""
    if not notes.exists():
        return None
    text = notes.read_text()
    sections = re.split(r"^## Intent:\s*", text, flags=re.M)[1:]
    for section in sections:
        heading, _, body = section.partition("\n")
        if heading.strip().strip('"') != intent.strip():
            continue
        ids = lambda line: [tok for tok in re.split(r"[,\s().;:]+", line) if tok in known_ids]  # noqa: E731
        picks = re.search(r"^Picks:\s*(.+)$", body, flags=re.M)
        nots = re.search(r"^Not:\s*(.+)$", body, flags=re.M)
        return (ids(picks.group(1)) if picks else [], ids(nots.group(1)) if nots else [])
    return None


def slug(intent: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", intent.lower()).strip("-")[:48] or "intent"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--intent", required=True, help="the project intent, one sentence")
    p.add_argument("--library", type=Path, default=LIBRARY_DIR, help="directory of brick JSON files (default: the sample library)")
    p.add_argument("--prompt", type=Path, default=PROMPT_FILE)
    p.add_argument("--schema", type=Path, default=SCHEMA_FILE)
    p.add_argument("--notes", type=Path, default=ROOT / "fixtures" / "propose_notes.md",
                   help="sealed notes, read only after the call to score the picks (never sent)")
    p.add_argument("--effort", default=EFFORT, choices=["minimal", "low", "medium", "high", "xhigh", "max"])
    p.add_argument("--max-output-tokens", type=int, default=MAX_OUT)
    p.add_argument("--out-dir", type=Path, default=OUT / "propose", help="where <slug>/propose.json lands (default out/propose)")
    p.add_argument("--dry-run", action="store_true", help="print the request and the estimate; send nothing")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    intent = args.intent.strip()
    if not intent or len(intent) > MAX_INTENT_CHARS:
        raise SystemExit(f"intent must be 1–{MAX_INTENT_CHARS} characters")
    template = args.prompt.read_text()
    if "{{INTENT}}" not in template or "{{LIBRARY}}" not in template:
        raise SystemExit(f"{args.prompt} must contain {{{{INTENT}}}} and {{{{LIBRARY}}}}")
    schema = json.loads(args.schema.read_text())
    library = load_library(args.library)
    if not library:
        raise SystemExit(f"no brick with rules in {args.library}")
    prompt = render_prompt(template, intent, library)
    request = build_request(prompt, schema, args.effort, args.max_output_tokens)

    client = Client(dry_run=args.dry_run)
    client.reserve(1)
    typical, worst = costs.estimate_spark([], len(prompt) + len(json.dumps(schema)), args.max_output_tokens)
    print(f"1 text request to {MODEL}; {len(library)} bricks, {sum(len(b['rules']) for b in library)} rules, "
          f"{len(prompt):,} prompt chars; effort={args.effort}")
    costs.print_estimate(MODEL, typical, worst)
    if not args.dry_run:
        costs.check_budget(costs.cost_usd(MODEL, worst))

    try:
        result = client.post_json("/responses", request)
    except ApiError as error:
        print(f"API error: {error}", file=sys.stderr)
        raise SystemExit(4 if 400 <= error.status < 500 else 5) from None
    if result is None:
        return
    usage = costs.Usage.from_response(result.body)
    status = result.body.get("status", "")
    notes = f"effort={args.effort}; bricks={len(library)}" + ("" if status == "completed" else f"; status={status}")
    call = costs.record_call(script=SCRIPT, model=MODEL, input_file=str(args.library), prompt_summary=f"propose: {intent[:40]}",
                             result=result, usage=usage, notes=notes + f"; notes={args.notes.name}")

    out_dir = args.out_dir / slug(intent)
    out_dir.mkdir(parents=True, exist_ok=True)
    text = output_text(result.body)
    report: dict[str, Any] = {"script": SCRIPT, "model": MODEL, "effort": args.effort, "status": status, "intent": intent,
                              "library": library, "prompt": prompt, "call": call.as_dict()}
    try:
        raw = json.loads(text)
        raw_picks = raw["picks"] if isinstance(raw, dict) and isinstance(raw.get("picks"), list) else None
        if raw_picks is None:
            raise ValueError("no picks array")
    except ValueError as error:
        report["raw_text"] = text
        report["response_body"] = result.body
        (out_dir / "propose.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"could not parse model output ({status}): {error}", file=sys.stderr)
        raise SystemExit(3) from None
    picks, dropped = validate_picks(raw_picks, library)
    report.update(raw_picks=raw_picks, picks=picks, dropped=dropped)
    sealed = expected_from_notes(args.notes, intent, {b["brick_id"] for b in library})
    if sealed is not None:
        expected, nots = sealed
        overlap = [p["brick_id"] for p in picks if p["brick_id"] in expected]
        wrong = [p["brick_id"] for p in picks if p["brick_id"] in nots]
        # Sealed rule: at least 2 of the sealed picks (both when only two are sealed), every quote valid, no "Not:" pick.
        need = min(2, len(expected)) if expected else 0
        ok = bool(expected) and len(overlap) >= need and not dropped and not wrong
        report["sealed"] = {"expected": expected, "not": nots, "overlap": overlap, "wrong": wrong, "pass": ok}
    (out_dir / "propose.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    for p in picks:
        print(f"    pick {p['brick_id']}: \"{p['quoted_rule'][:90]}\" — {p['why'][:120]}")
    for d in dropped:
        print(f"    dropped {d['brick_id']}: {d['reason']}")
    if sealed is not None:
        s = report["sealed"]
        print(f"    sealed notes expect {s['expected']}; overlap {s['overlap']}"
              + (f"; picked from Not: {s['wrong']}" if s['wrong'] else "") + f"; {'PASS' if s['pass'] else 'MISS'}")
    else:
        print("    (no sealed notes for this intent; judge by hand)")
    print(f"    -> wrote {out_dir / 'propose.json'}")


if __name__ == "__main__":
    main()
