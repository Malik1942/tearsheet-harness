# Meta Model API evaluation report

Fill this in after real runs. Numbers come from the per-call stdout lines, the `out/<stem>/*.json` files, and `python -m meta_eval.costs summary`.

- Date / model IDs: `sam-3.1`, `muse-spark-1.3` (effort: ___)
- Fixtures used: ___
- Spend so far (ledger total): $___ of $150

## SAM 3.1: image

Targets are the objects you labeled. A hit is a mask that covers the target and only the target. Note target size in px to judge small-object accuracy.

| Image | Target (your label, size px) | Prompt (text / point / box) | Hit / miss | # masks | Best conf | Latency ms | $ |
|---|---|---|---|---|---|---|---|
| | | | | | | | |
| | | | | | | | |

Observations (false positives, prompt wording that worked or failed, behaviour on small objects):

-

## SAM 3.1: video

| Clip | Prompt | Frames billed | Tracks | % frames tracked | Mean conf | Max centre jump px | Wall s | $ | $ per 10 s |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |

Tracking stability and drift (id switches, dropouts, re-entry, occlusion; check `sam_video_overlay.mp4`):

-

## Muse Spark: locate

Coordinate accuracy is your eyeballed box vs the Spark box, both in pixels of the sent image. IoU ≥ 0.5 counts as a usable hit.

| Image | Label | Your box (px) | Spark box_px_sent | IoU | Conf | In tok | Out tok (reasoning) | Latency ms | $ |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |

Observations (missed objects, hallucinated objects, box tightness, effect of `--effort`):

-

## Muse Spark: describe-json (optional)

| Image | Schema | Valid JSON? | Useful relationships? | In / out tok | $ |
|---|---|---|---|---|---|
| | | | | | |

## Live probe

| Backend | Mode | Sent res | Latency p50 / p95 ms | Updates/min | $/min | Tracker drift (IoU < 0.5) |
|---|---|---|---|---|---|---|
| sam | | | | | | |
| spark | | | | | | |

UX pattern this supports. The API has no live video input, so each update is one request:

- **Continuous overlay** (auto `--every N`, CSRT between updates): viable if ___
- **Snapshot-on-demand** (SPACE, result in ~___ ms): viable if ___

## What this means for the 38-hour build

- Which model for which job: ___
- Per-interaction cost and the projected demo/day spend: ___
- Latency budget the UX must hide: ___
- Prompts or settings to lock in: ___
- Risks and fallbacks (zero matches, drift, rate limits): ___

## Gate (Bricks)

Procedure and pass/fail rule: `docs/GATE.md`. Settings sealed in `fixtures/gate_notes.md`.

Smoke call (not one of the three): photo ___, status ___, latency ___ ms, in/out tokens ___/___, $___, schema accepted: yes / no (what changed: ___)

| Photo | Sealed reason | Hit as (measurement id / relation id / hypothesis only / miss) | Status | Effort | MAX_OUT | MAX_SIDE | Sent px | Latency ms | In tok | Out tok (reasoning) | $ | Boxes usable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | | | | |
| | | | | | | | | | | | | |
| | | | | | | | | | | | | |

Result: ___ of 3 hits. Gate: pass / fail. Prompt used: real `02_extract_prompt.md` / stand-in. Calls outside the judged set (second-effort pass, re-runs after a non-completed status, timeouts not in the ledger): ___

Calls outside the judged set, by hand (the app does not write ledger.csv): 2026-11-02 ~15:05 PT, one live extraction of `_smoke.jpg` through the Bricks app (`/api/extract`, effort medium, cap 12000): status completed, 33.9 s wall clock in the browser, 3381 in / 2931 out tokens, about $0.017. Running total since the harness was built: 12 calls, about $0.20.
2026-11-02 ~19:45 PT: one live extraction through the PUBLIC deployment (tearsheet-malik1942s-projects.vercel.app/api/extract, prompt v3, effort medium) on g1: completed, 21.3 s, 4191 in / 2381 out, about $0.015. Not in ledger.csv. Running total: 23 calls, about $0.40.
