"""Pricing (parsed from docs/ENDPOINTS.md), per-call cost, the call ledger, and `summary`.

    python -m meta_eval.costs summary
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import cache
from typing import Any

from .client import ROOT, ApiResult

PRICING_DOC = ROOT / "docs" / "ENDPOINTS.md"
LEDGER = ROOT / "ledger.csv"
BUDGET_USD = 150.0
LEDGER_FIELDS = [
    "timestamp", "script", "model_id", "input_file", "prompt_summary", "images_sent", "frames_sent",
    "input_tokens", "output_tokens", "latency_ms", "est_cost_usd", "notes",
]

# Dry-run token estimate for Muse Spark images (ENDPOINTS.md, decision 9): the docs measure
# ~1,300-1,500 tokens for a ~1280 px image and ~110 tokens of fixed prompt overhead.
TOKENS_PER_REF_IMAGE = 1500
REF_IMAGE_AREA = 1280 * 960
MIN_IMAGE_TOKENS = 3
PROMPT_OVERHEAD_TOKENS = 110
CHARS_PER_TOKEN = 4
TYPICAL_OUTPUT_TOKENS = 800


@dataclass(frozen=True)
class Price:
    input_per_1m: float
    cached_input_per_1m: float
    output_per_1m: float
    per_image: float
    per_frame: float
    min_frames: int


@cache
def pricing() -> dict[str, Price]:
    """Parse the table between the pricing markers in ENDPOINTS.md."""
    block = PRICING_DOC.read_text().split("<!-- pricing:begin -->", 1)[1].split("<!-- pricing:end -->", 1)[0]
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in block.strip().splitlines()]
    header, body = rows[0], rows[2:]  # rows[1] is the |---| separator
    table = {}
    for row in body:
        record = dict(zip(header, row, strict=True))
        model = record.pop("model")
        table[model] = Price(**{k: int(v) if k == "min_frames" else float(v) for k, v in record.items()})
    return table


@dataclass
class Usage:
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    images: int = 0
    frames: int = 0

    @classmethod
    def from_response(cls, body: dict[str, Any]) -> Usage:
        usage = body.get("usage") or {}
        return cls(
            input_tokens=usage.get("input_tokens") or 0,
            cached_tokens=(usage.get("input_tokens_details") or {}).get("cached_tokens") or 0,
            output_tokens=usage.get("output_tokens") or 0,
            reasoning_tokens=(usage.get("output_tokens_details") or {}).get("reasoning_tokens") or 0,
            images=usage.get("images_processed") or 0,
            frames=usage.get("video_frames_processed") or 0,
        )

    def describe(self, fps: float | None = None) -> str:
        tokens = f"in={self.input_tokens} out={self.output_tokens} tok"
        if self.cached_tokens or self.reasoning_tokens:
            tokens += f" (cached {self.cached_tokens}, reasoning {self.reasoning_tokens})"
        parts = [tokens]  # images/frames are SAM billing units; Spark images are billed as tokens
        if self.images:
            parts.append(f"images={self.images}")
        if self.frames:
            parts.append(f"frames={self.frames}" + (f", seconds={self.frames / fps:.1f}" if fps else ""))
        return ", ".join(parts)


@dataclass
class CallRecord:
    model: str
    latency_ms: float
    request_bytes: int
    retries: int
    usage: Usage
    cost_usd: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def cost_usd(model: str, usage: Usage) -> float:
    price = pricing()[model]
    frames = max(usage.frames, price.min_frames) if usage.frames else 0
    uncached = max(usage.input_tokens - usage.cached_tokens, 0)
    token_cost = (
        uncached * price.input_per_1m
        + usage.cached_tokens * price.cached_input_per_1m
        + usage.output_tokens * price.output_per_1m
    ) / 1e6
    return token_cost + usage.images * price.per_image + frames * price.per_frame


def estimate_image_tokens(width: int, height: int) -> int:
    return max(MIN_IMAGE_TOKENS, round(TOKENS_PER_REF_IMAGE * width * height / REF_IMAGE_AREA))


def estimate_spark(sizes: list[tuple[int, int]], text_chars: int, max_output_tokens: int) -> tuple[Usage, Usage]:
    """(typical, worst-case) usage for one Muse Spark call."""
    input_tokens = (
        PROMPT_OVERHEAD_TOKENS + text_chars // CHARS_PER_TOKEN + sum(estimate_image_tokens(w, h) for w, h in sizes)
    )
    typical = Usage(input_tokens=input_tokens, output_tokens=min(TYPICAL_OUTPUT_TOKENS, max_output_tokens))
    worst = Usage(input_tokens=input_tokens, output_tokens=max_output_tokens)
    return typical, worst


def print_estimate(model: str, usage: Usage, worst: Usage | None = None, fps: float | None = None) -> None:
    line = f"  est. cost [{model}]: ${cost_usd(model, usage):.4f}  ({usage.describe(fps)})"
    if worst is not None:
        line += f"; worst case ${cost_usd(model, worst):.4f} at {worst.output_tokens} output tokens"
    print(line)


def ledger_rows() -> list[dict[str, str]]:
    if not LEDGER.exists():
        return []
    with LEDGER.open(newline="") as f:
        return list(csv.DictReader(f))


def spent_usd() -> float:
    return sum(float(row["est_cost_usd"]) for row in ledger_rows())


def check_budget(planned_usd: float) -> None:
    """Refuse to start a run whose worst case would push the ledger past the hard cap."""
    spent = spent_usd()
    if spent + planned_usd > BUDGET_USD:
        raise SystemExit(f"budget: ${spent:.2f} spent + ${planned_usd:.2f} planned exceeds ${BUDGET_USD:.0f} cap")


def record_call(
    *,
    script: str,
    model: str,
    input_file: str,
    prompt_summary: str,
    result: ApiResult,
    usage: Usage,
    images_sent: int = 0,
    frames_sent: int = 0,
    notes: str = "",
    fps: float | None = None,
) -> CallRecord:
    """Price one real call, append it to the ledger, and print the per-call line."""
    cost = cost_usd(model, usage)
    extra = [notes, f"retries={result.retries}" if result.retries else "",
             f"reasoning_tokens={usage.reasoning_tokens}" if usage.reasoning_tokens else ""]
    row = {
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
        "script": script,
        "model_id": model,
        "input_file": input_file,
        "prompt_summary": prompt_summary,
        "images_sent": images_sent,
        "frames_sent": frames_sent,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "latency_ms": round(result.latency_ms),
        "est_cost_usd": f"{cost:.6f}",
        "notes": "; ".join(n for n in extra if n),
    }
    new_file = not LEDGER.exists()
    with LEDGER.open("a", newline="") as f:
        writer = csv.DictWriter(f, LEDGER_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
    print(f"  [{model}] {prompt_summary}: latency {result.latency_ms:.0f} ms | {usage.describe(fps)} "
          f"| est. cost ${cost:.4f}")
    return CallRecord(model, round(result.latency_ms, 1), result.request_bytes, result.retries, usage, cost)


def _column(rows: list[dict[str, str]], name: str) -> float:
    return sum(float(row[name] or 0) for row in rows)


def summary() -> None:
    rows = ledger_rows()
    if not rows:
        print(f"{LEDGER.name} is empty: no real calls yet.")
        return
    by_model: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_model[row["model_id"]].append(row)

    print(f"{'model':<28}{'calls':>6}{'total $':>11}{'$/call':>10}{'mean ms':>9}"
          f"{'in tok':>10}{'out tok':>10}{'images':>8}{'frames':>8}")
    for model, group in sorted(by_model.items()):
        total = _column(group, "est_cost_usd")
        mean_ms = _column(group, "latency_ms") / len(group)
        print(f"{model:<28}{len(group):>6}{total:>11.4f}{total / len(group):>10.4f}{mean_ms:>9.0f}"
              f"{_column(group, 'input_tokens'):>10.0f}{_column(group, 'output_tokens'):>10.0f}"
              f"{_column(group, 'images_sent'):>8.0f}{_column(group, 'frames_sent'):>8.0f}")
    spent = spent_usd()
    print(f"\nTOTAL {len(rows)} calls, ${spent:.4f} of ${BUDGET_USD:.0f} cap (${BUDGET_USD - spent:.2f} left)")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m meta_eval.costs", description="Ledger totals by model.")
    parser.add_argument("command", choices=["summary"])
    parser.parse_args(argv)
    summary()


if __name__ == "__main__":
    main()
