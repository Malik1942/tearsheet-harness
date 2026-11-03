# Gate: does Muse Spark extract what you liked?

Monday 2026-11-03, 10:00. This run decides whether the Bricks build starts.

**Pass:** three valid bricks, and at least two of them contain the pre-registered reason you saved the photo, as a measurement or a relation, not only as a hypothesis.
**Fail:** the reason is missing from two of the three photos. The direction stops.

**Valid** at the gate means the response came back with `status: completed` and the JSON parsed. Constrained decoding guarantees the shape of a completed response. A truncated or errored response is not a brick and is re-run as described in section 3. A valid brick without the reason is a miss.

All commands run from `meta-eval/`. Photo paths are `fixtures/images/<name>`.

## 1. Seal (no calls, no key)

Everything in this section is written down before any photo is sent, and not edited afterwards.

1. **Photos.** Drop the three photos into `fixtures/images/` as jpg or png, each with a distinct file name. Names starting with `_` are ignored by the gate script. iPhone HEIC files are not read by the harness; convert first:
   ```bash
   sips -s format jpeg ~/Downloads/IMG_1234.HEIC --out fixtures/images/poster.jpg
   ```
2. **Notes.** In `fixtures/gate_notes.md`, one line per photo on why you saved it, and whether you expect the extraction to recover it as a measurement or as a relation.
3. **Settings.** Also in `fixtures/gate_notes.md`: the effort (`EFFORT`, default low), the output cap (`MAX_OUT`, default 12000) and the sent long side (`MAX_SIDE`, default 2048). The effort is the one `api/extract.ts` will send; the gate validates that setting and no other. All three photos run at these settings and only that set is judged.
4. **Prompt and schema.** `fixtures/prompts/extract_brick.md` is the author's extraction prompt (supplied 2026-11-02) and `fixtures/schemas/brick.json` mirrors the author's schema with three additions that do not change what the model can say: `additionalProperties: false` on every object, a `title` the harness uses as the schema name, and `none` listed in the `parameter` description because the prompt allows it. The harness sends the prompt as the text part of the user message next to the image, which is where the API reads images; there is no separate system message. Keep the schema strict-compatible (object root, `additionalProperties: false` on every object, every key required, no recursion, depth at most 10) so `api/extract.ts` can turn `strict: true` on later; the gate itself sends without `strict`. Any edit to either file after the smoke call re-opens the acceptance risk. Record both files' checksums in the seal:
   ```bash
   shasum -a 256 fixtures/prompts/extract_brick.md fixtures/schemas/brick.json
   ```
5. **Dry-run.** `scripts/gate.sh`. Nothing is sent. Check the printed request: the prompt text, schema name `BrickExtraction`, the image sent at a long side of `MAX_SIDE` or less, `max_output_tokens`, `store: false`, and the cost estimate. The "worst case" figure is the planning number; "typical" assumes 800 output tokens, which is small for a brick.

## 2. Smoke call (one real call, decided 2026-11-02; needs your go on the day)

The smoke call runs after the seal and before the three sealed photos. No request has ever left this harness, so the key, the model id, the API's acceptance of the schema, the response envelope and the ledger write are all unverified. One call on a photo that is **not** one of the three settles that before the sealed run. Use a fourth real photo saved as `fixtures/images/_smoke.jpg` (the underscore keeps it out of the gate glob; add it to the seal); the synthetic placeholder only proves the plumbing and gives unrepresentative tokens and latency.

```bash
export META_API_KEY=...        # or put it in .env; it is never printed or written
scripts/gate.sh --send fixtures/images/_smoke.jpg
```

Check: HTTP 200, `status: "completed"`, a parsed `result` in `out/_smoke/spark_vision.json`, every `relations[].parameter` inside the enum, `reasoning_tokens` well under `MAX_OUT`, non-zero `input_tokens`, `output_tokens` and cost both in the printed line and in `ledger.csv` (a usage-shape mismatch would silently record $0), region boxes on `spark_overlay.png` sitting on what they claim, and the latency. The smoke is valid only for the exact prompt and schema it was sent with: edit either afterwards and the acceptance risk is back, so run it after the seal is complete. If the API returns 400 naming the schema: for `minimum`, `maximum`, `minItems` or `maxItems`, delete those keywords (the harness clamps boxes itself); for `enum`, keep `type: string`, move the allowed keys into the `parameter` description, and check membership by hand when judging. Worst case about $0.06. Record it in `out/REPORT.md` as a non-gate call.

## 3. The run (three real calls)

Only after the smoke call came back `completed` with the checks above.

```bash
scripts/gate.sh --send
```

- One process per photo, so one call per photo; the harness call guard and the $150 budget guard apply to every run. Worst case per photo at `MAX_OUT=12000` is about $0.06 by the dry-run estimate, which scales image tokens linearly with area; the ledger's `usage.input_tokens` is the real figure. Check it after the first photo.
- Results: `out/<stem>/spark_vision.json` (`result` holds the brick, `call` the usage, cost and latency, `status` the API status), `out/<stem>/sent.jpg` (the exact pixels sent; `box_1000` refers to this image) and `out/<stem>/spark_overlay.png` with the region boxes drawn.
- A failed photo does not stop the others. The script lists failed photos at the end and exits 1. Re-send **only** those, by path; a bare `--send` would re-sample the photos that already succeeded and overwrite their results.
- A `status` other than `completed` is not a brick. The full response is saved under `response_body` in `spark_vision.json`; compare `call.usage.output_tokens` with `MAX_OUT` to confirm the cap was the cause, then re-run that photo at the sealed effort with a higher cap: `EFFORT=<sealed> MAX_OUT=16000 scripts/gate.sh --send fixtures/images/<name>` (worst case about $0.08). Any other reason: read the body before re-running.
- The harness gives up at 300 s per call (`TIMEOUT_S` in `client.py`). A timeout or an HTTP error writes nothing to `ledger.csv` even though the call may have been billed; note it in the report by hand.

## 4. Judging

For each photo, open `result.measurements` and `result.transferable_relations` next to the sealed note (the pre-registration; the author's `01_preregister.md` and `fixtures/gate_notes.md` serve the same purpose).

- **Hit:** the note's reason is stated in substance as a measurement or a transferable relation.
- **Fluent but unsupported:** the reason appears only under `hypotheses`, or in a hypothesis whose `rests_on` is empty or points at a measurement id that does not exist. Not a hit.
- **Half hit:** the relation is right but the region box for its measurement sits on the wrong area. Count it separately, and watch that photo closely when the composition panel is built.
- A valid brick without the reason is a miss.

Check every region box on `spark_overlay.png` against `sent.jpg`. Record each photo's tokens and latency: the latency is also the wait a user will see when swapping one material in the product.

Never re-run a single photo at a different effort or resolution after a miss: a second draw on misses alone raises the pass rate by resampling, not by capability, and leaves no single setting validated. If you also want the other effort's latency and tokens, copy the three `out/<stem>/` folders aside first (`cp -R out/<stem> out/judged_<effort>_<stem>`; a second run overwrites them), then run all three at the other effort (`EFFORT=medium scripts/gate.sh --send`, three more calls, about $0.17 worst case). Those bricks never count toward pass or fail; they only inform which effort `api/extract.ts` sends if the judged set passed.

Record per photo in the gate table of `out/REPORT.md`: hit or miss and where it appeared, status, effort, `MAX_OUT`, `MAX_SIDE`, sent size, latency, input and output tokens with reasoning tokens, cost, and whether the boxes are usable.

## 5. What the numbers feed

- **Latency per photo** decides whether a synchronous `/api/extract` fits. Vercel's function ceiling with Fluid compute is 300 s on Hobby (the default equals the maximum) and 800 s on Pro (set `maxDuration` explicitly); check the plan's current limits. The brief retries once inside the function, so compare twice the slowest photo's latency plus a margin against the ceiling. Above it, move the retry to the browser or use the Meta API's `background: true` mode, which ENDPOINTS.md only names.
- **Input and output tokens** from the ledger set the per-call cost line in the brief, valid for images sent at the sealed `MAX_SIDE`.
- **The request shape** printed by the dry-run is what `api/extract.ts` must send: `text.format` json_schema, `reasoning.effort` as sealed, `max_output_tokens`, `store: false`, and the image prepared the same way: EXIF-upright, long side at most the sealed `MAX_SIDE`, JPEG (q95 here; a browser canvas at about 0.9 is fine; keep PNG as PNG), inline as a base64 data URL. The browser must do that downscale before upload: a raw phone photo as base64 exceeds Vercel's 4.5 MB request body cap, costs several times the image tokens, and leaves it to Spark whether the 0-1000 grid is EXIF-rotated. `photo.width` and `photo.height` in the Brick are the sent dimensions (`sent_sizes` in `spark_vision.json`).
- **Region box quality** decides whether Spark's boxes are enough for v1, which keeps SAM out of v1.
- **Fixtures for the app:** `out/<stem>/spark_vision.json` plus `sent.jpg` load as the three demo bricks without new calls.
