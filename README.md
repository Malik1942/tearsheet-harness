# meta-eval

A small, cost-accounted harness for testing **SAM 3.1** and **Muse Spark vision** on the Meta Model API with your own images and videos.

- Every CLI sends one request per call (video: upload + segment), unless you pass `--dry-run`, which sends nothing.
- Each real call is logged to `ledger.csv`.

API facts, limits, pricing and the decisions behind them are in [docs/ENDPOINTS.md](docs/ENDPOINTS.md).

## Setup

You need Python ≥ 3.11 and ffmpeg (`brew install ffmpeg`). `sam_video` uses ffmpeg to trim and encode clips.

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r pyproject.toml
source .venv/bin/activate
export META_API_KEY=...        # or put it in .env (gitignored); it is never printed or written
```

## The three commands

```bash
python -m meta_eval.sam_image fixtures/images/x.jpg --text "electrical cord" --text "rug edge" [--point x,y] [--box x1,y1,x2,y2] [--dry-run]
python -m meta_eval.sam_video fixtures/videos/x.mp4 --text "basketball" --max-frames 300 [--dry-run]
python -m meta_eval.spark_vision fixtures/images/x.jpg --task locate --labels "resistor,LED,Arduino board" [--dry-run]
```

Each command prints latency, usage (tokens, images, frames/seconds) and the estimated USD per call. Outputs go to `out/<stem>/`:

| Command | Files |
|---|---|
| `sam_image` | `sam_image.json` (prompts, masks with box-local COCO RLE, boxes, confidences, latency), `sam_image_overlay.png` |
| `sam_video` | `sam_video.json` (per-frame boxes per object id), `track_summary.json`, `sam_video_overlay.mp4`, `sent.mp4` (the exact clip uploaded) |
| `spark_vision` | `spark_vision.json` (the report: task, model, status, prompt, call usage and cost; `result` holds the located-object list `[{label, box_1000, confidence, notes, box_px_sent}]` for locate or the parsed JSON for describe-json; on a parse failure `raw_text` and `response_body`), `sent.jpg` or `sent.png` (the exact image sent), `spark_overlay.png` |

Things to know:

- **`sam_image`**:
  - Each `--text` is a separate request: the API takes one concept per request, and each is billed as one image ($0.0025).
  - All `--point`/`--box` flags share one extra request.
  - Coordinates are pixels of the upright original image. Box corners are inclusive.
- **`sam_video`**:
  - Keeps the first `--max-frames` frames (default 300) and bills at least 50 frames ($0.20 per 1,000 frames, so 10 s at 30 fps is $0.06).
  - Re-runs reuse the uploaded `file_id` (cached in `out/<stem>/upload.json`).
- **`spark_vision`**:
  - Defaults: `--model muse-spark-1.3 --effort low --max-output-tokens 4000 --max-side 1280`.
  - Reasoning tokens are billed as output.
  - Free-form structure: `--task describe-json --schema fixtures/schemas/relationships.example.json`, or `--schema my_pkg.schemas:MyModel` for a pydantic model. Any `box_1000` in the result is drawn on the overlay.
- **Live probe** (no streaming in the API, so it sends single frames):
  ```bash
  python -m meta_eval.live_probe --backend sam --text "resistor" [--every 3] [--max-calls 10] [--track] [--dry-run]
  python -m meta_eval.live_probe --backend spark --labels "resistor,LED" --every 3
  ```
  - SPACE sends a frame; `--every N` (N ≥ 2) sends one automatically.
  - At most one request is in flight, and `--max-calls` (default 10) hard-caps the session.
  - Frames are downscaled to ≤ 1280 px.
  - `--source path.mp4` replaces the webcam with a file.
  - Spark defaults to `--effort minimal` here, because latency matters.
  - At exit it prints p50/p95 latency, updates/min, total cost and projected $/min.

## Dry-run flow

1. Drop files in `fixtures/images/` and `fixtures/videos/`.
2. Run the command with `--dry-run`. It prints the request (headers with the key redacted; base64 media shown as size + hash) and the cost estimate. No key is needed and nothing is sent.
3. Drop `--dry-run` to send. Before sending, each run checks:
   - **Call guard**: `MAX_CALLS_PER_RUN = 3` in `meta_eval/client.py`. A run that would need more requests aborts before sending anything. The live probe uses its own `--max-calls`.
   - **Budget guard**: the ledger total plus this run's worst case must stay under $150 (`BUDGET_USD` in `costs.py`).
4. Check spend:
   ```bash
   python -m meta_eval.costs summary
   ```

Retries: at most 2, only on 429/500/502/503, honouring `Retry-After`. 4xx and 504 are never retried (see ENDPOINTS.md).

Fill in [out/REPORT.md](out/REPORT.md) after real runs.

## Gate run (Bricks)

`scripts/gate.sh` runs one Muse Spark extraction per photo in `fixtures/images/` with the brick schema (`fixtures/schemas/brick.json`) and the extraction prompt (`fixtures/prompts/extract_brick.md`). It is a dry-run unless you pass `--send`. Knobs are environment variables: `EFFORT` (low), `MAX_OUT` (12000), `MAX_SIDE` (2048), `PROMPT_FILE`, `SCHEMA_FILE`. A failing photo does not stop the others. The procedure, the pass/fail rule and what to record are in [docs/GATE.md](docs/GATE.md); seal your notes and settings in `fixtures/gate_notes.md` first.

## Proposal set

`scripts/propose.sh` dry-runs one text call per intent against the sample library; `--send` makes the calls (needs the sealed `fixtures/propose_notes.md`, see `docs/PROPOSE.md`). Prompt `fixtures/prompts/propose.md` and schema `fixtures/schemas/propose.json` are the product's, rendered identically.
