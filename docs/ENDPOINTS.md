# Meta Model API: endpoints, schemas, limits, pricing

Read from the official docs on 2026-11-01. Sources (all under `https://dev.meta.ai/docs/`):
`overview`, `authentication`, `models`, `pricing-rate-limits`, `media-segmentation`, `sam/overview`,
`sam/segmenting`, `sam/reading-segmentation`, `sam/client-libraries`, `image-understanding`,
`structured-output`, `reasoning`, `file-handling`, `error-handling`, `protocols/responses`,
`api-reference/responses/schemas`, `token-counting`.

## Base URL and auth

- Base URL: `https://api.meta.ai/v1` (matches the briefing).
- Auth: `Authorization: Bearer <key>`. Keys look like `LLM_<numeric id>_<secret>`.
- The docs use the env var `MODEL_API_KEY`. **This harness reads `META_API_KEY`** (as you asked).
- Rate limits are **per team**, not per key.

## Model IDs

| Use | Model ID | Notes |
|---|---|---|
| Segmentation (image + video) | `sam-3.1` | One model for stills and clips. Output is special-token text, not JSON |
| Vision / structured JSON | `muse-spark-1.3` | Latest, "recommended for new work". Standard mode, so your content is not used for training |
| Vision (cheaper) | `muse-spark-1.3-contributor` | Same model at much lower prices, but **Meta may train on your prompts/images** |
| Older | `muse-spark-1.2`, `muse-spark-1.1`, `muse-spark-1.2-contributor` | 1.1 is Standard only |

Muse Spark is a reasoning model with a 1,048,576-token context. It accepts text, image, video, audio and PDF.

## SAM 3.1: request

`POST /v1/responses`, one user message with exactly **one prompt + one media part**:

```json
{
  "model": "sam-3.1",
  "input": [{"type": "message", "role": "user", "content": [
    {"type": "input_text", "text": "electrical cord"},
    {"type": "input_image", "image_url": "data:image/jpeg;base64,..."}
  ]}],
  "metadata": {"include_confidence": "true", "mask_encoding": "lossless"},
  "stream": false
}
```

- **Media**:
  - `input_image.image_url` is a public URL or a base64 data URL.
  - `input_video.video_url` is a URL or data URL, or use `input_video.file_id` after a Files API upload.
- **Concept (text) prompt**:
  - A short noun phrase naming **one** concept per request.
  - Lists ("a, b", "a; b", "a + b") return zero matches. "and", a newline, or a second `input_text` segments only one of the concepts.
  - Avoid commands, questions, negation, OR, and spatial phrases ("on the left" is only partly honored).
  - Attributes narrow the match predictably ("red square").
  - Plurals, case and punctuation are ignored.
- **Box / point prompts** (no concept phrase in the same text, never both):
  - Written in the output grammar inside `input_text`: `<0f>1<|box;x1=..;y1=..;x2=..;y2=..;w=W;h=H|>,2<|point;x=..;y=..;w=W;h=H|>-<|point;...|>`.
  - `<Nf>` is the frame (images use `<0f>` only).
  - `id` is an integer you choose; each id appears once per frame.
  - At most one box per object per frame. `x2`/`y2` are **inclusive**.
  - A leading `-` makes a **negative point**. Only points can be negative.
  - Coordinates are **source pixels of the media as displayed** (after EXIF or video rotation). `w`/`h` = media size.
  - A `w`/`h` with the wrong aspect ratio returns 400.
  - At most **16 prompted objects** per request.
  - `meta_sam_parser.build_object_prompt` builds this text.
- **Metadata** (all values are strings):
  - `include_confidence: "true"` adds `c` (0–1) on box and mask.
  - `mask_encoding: "lossless"` (default, `~` marker) or `"one_bit"` (`!` marker, several times smaller). Box/point prompts **always** return `one_bit`. (Not what the live API did on an image box prompt; see [Live API checks](#live-api-checks-2026-11-02).)
  - `propagation_direction: both | forward | backward` applies to video box/point prompts. It is measured from the earliest prompt frame.
- **Streaming** is optional. SSE `response.output_text.delta` sends one line per frame and ends with `response.completed`. Non-streaming returns the same text in one response.

## SAM 3.1: response format

- Output is plain text in the `output_text` lane: **one line per frame**. A frame with no objects emits no line, so frame indices can skip.
- Line: `<Nf>id<|box;x1=..;y1=..;x2=..;y2=..;w=W;h=H[;c=..]|><|mask;x=0;y=0[;c=..];data=H,W,<enc><base85>|>,id<|box..|><|mask..|>...`
- **Boxes**: xyxy, source pixels (not normalized), `x2`/`y2` inclusive. `w`/`h` = frame size, repeated on every record.
- **Masks**: not RLE, PNG or polygons. They are a custom raster in a base85 variant (not base64).
  - `data=H,W,` is height first. The raster is **box-local** (its size equals the box size).
  - Decode with `meta_sam_parser.decode_mask_to_raster`. `decode_mask_to_rle` gives COCO RLE; `decode_mask_to_svg_path` gives a polygon path.
- **Confidence**: `c` appears only with `include_confidence`. It is the same on box and mask, and can differ per frame.
- **Object ids** are stable across frames while the object stays in view. They are sparse, not 0-based dense. Don't trust ids across exit, re-entry or full occlusion.
- **Zero matches** is not an error: the response completes with empty `output_text`.
- **Usage**: `usage.images_processed` (image) or `usage.video_frames_processed` (video). This is what gets billed.
- Results vary slightly between identical runs: box coordinates, mask edges, and occasionally which objects are found.

## SAM 3.1: video

- Containers: **MP4/MOV with H.264, H.265 or MPEG-4**. VP9/WebM are rejected.
- Up to **15,000 frames (about 10 min) per request**. Video tracks up to **16 objects per frame**. Image requests return every matching instance.
- Upload is `POST /v1/files` (multipart, `purpose=user_data`). It is **synchronous**: a 200 means the file is usable, so there is **no polling**. Reference the upload with `input_video.file_id`.
  - Optional `expires_after[anchor]=created_at`, `expires_after[seconds]` between 3600 and 2592000.
  - Files **never expire by default**. Team storage is capped at 100 GiB. `DELETE /v1/files/{id}` removes a file.
- An MP4 whose moov atom is at the end gets remuxed (stream copy) server-side. Export with `-movflags +faststart` to avoid that.
- Concept prompts process the **whole clip** and return frames in ascending order.

## Muse Spark vision: request

`POST /v1/responses` (the docs recommend it for images). Chat Completions also works and wraps the image as `image_url: {url}`.

```json
{
  "model": "muse-spark-1.3",
  "input": [{"type": "message", "role": "user", "content": [
    {"type": "input_text", "text": "<grounding prompt>"},
    {"type": "input_image", "image_url": "data:image/jpeg;base64,..."}
  ]}],
  "text": {"format": {"type": "json_schema", "name": "LocateResult", "schema": {...}}},
  "reasoning": {"effort": "low"},
  "max_output_tokens": 4000,
  "store": false
}
```

- **Images**:
  - Up to **50 images per request**; more returns 400.
  - 50 MB per inline image, 1 GiB via the Files API.
  - Accepted types: jpeg, png, gif, webp, x-icon.
  - Images are only read in **user** messages.
- **Coordinates**:
  - The model reports positions on a **normalized 0–1000 grid** of the image *as sent*. (0,0) is top-left; x goes right, y goes down.
  - It may emit values slightly out of range (e.g. 1001) for objects touching the edge. Clamp them.
  - Pixel conversion: `x_px = x * width / 1000`.
- **Structured output**:
  - Use `text.format = {type: "json_schema", name, schema, strict?}` on Responses (`response_format` is the Chat Completions equivalent).
  - Decoding is constrained, so the output always conforms, even with `strict: false`.
  - `strict: true` additionally checks the schema against the strict subset: the root is a plain object, `additionalProperties: false`, and every key is required.
  - Limits: depth 10, 5,000 properties. Recursive schemas return 400.
- **Grounding prompt advice** (from the docs):
  - List the objects and ask for one output shape (point / box / count).
  - Lead with "You are an object grounding expert" and "do not miss any objects".
  - Keep the system prompt minimal.
- **Reasoning**: `reasoning.effort` is one of minimal | low | medium | high | xhigh | max. `"none"` returns 400 on Spark.
  - Reasoning tokens are **billed as output tokens** and count against `max_output_tokens` (minimum 16).
  - The docs advise `max_output_tokens` ≥ 4000, otherwise the visible output can come back empty with an incomplete status.
- **Usage**: `usage.input_tokens`, `input_tokens_details.cached_tokens`, `output_tokens`, `output_tokens_details.reasoning_tokens`, `total_tokens`.
- **Image tokens** scale with resolution. Per the docs: a 1×1 image is about 3 tokens, a ~1280 px image about 1,300–1,500 tokens, plus about 110 tokens of fixed prompt overhead.
  - `POST /v1/responses/input_tokens` counts exactly. Per the docs it is for checking context fit, not for estimating billing.
- Logprobs are not supported (400). Leave `temperature`/`top_p` unset.

## Errors and retries

| Status | Meaning | Harness behaviour |
|---|---|---|
| 400 | Invalid prompt, metadata or schema; permanent for that request | No retry |
| 401/403/404 | Auth, access, or `model_not_found` | No retry |
| 413 | Payload too large (e.g. ~16 MB body with `store=true`) | No retry. We send `store: false` |
| 429 | Rate limit, with `Retry-After` | Retry (max 2), honouring `Retry-After` |
| 500 | Includes "model output parsing failure"; safe to retry | Retry (max 2) |
| 502/503 | Overload or unavailable, with `Retry-After` (60 s for overload) | Retry (max 2), honouring `Retry-After` (capped at 60 s) |
| 504 | Gateway timeout. Docs: "Do not simply retry"; use `background: true` | **No retry** (deviation from "all 5xx"; see Decisions) |

An unknown path returns 404 with an empty body (no JSON envelope).

## Rate limits (per team)

| Model | RPM | TPM |
|---|---|---|
| `sam-3.1` | 3,000 | none |
| `muse-spark-1.3` / `1.2` / `1.1` | 3,000 | 4,000,000 |
| `muse-spark-1.3-contributor` / `1.2-contributor` | 150 | 3,000,000 |

## Pricing

Machine-readable: `meta_eval/costs.py` parses this table, so keep the header and markers intact.
Token prices are USD per 1M tokens. `per_image` and `per_frame` are USD per unit. `min_frames` is the per-request video minimum.

<!-- pricing:begin -->
| model | input_per_1m | cached_input_per_1m | output_per_1m | per_image | per_frame | min_frames |
|---|---|---|---|---|---|---|
| muse-spark-1.3 | 1.25 | 0.15 | 4.25 | 0 | 0 | 0 |
| muse-spark-1.2 | 1.25 | 0.15 | 4.25 | 0 | 0 | 0 |
| muse-spark-1.1 | 1.25 | 0.15 | 4.25 | 0 | 0 | 0 |
| muse-spark-1.3-contributor | 0.10 | 0.002 | 0.20 | 0 | 0 | 0 |
| muse-spark-1.2-contributor | 0.10 | 0.002 | 0.20 | 0 | 0 | 0 |
| sam-3.1 | 0 | 0 | 0 | 0.0025 | 0.0002 | 50 |
| files | 0 | 0 | 0 | 0 | 0 | 0 |
<!-- pricing:end -->

In docs units:
- SAM 3.1 image is **$2.50 / 1,000 images**. SAM 3.1 video is **$0.20 / 1,000 frames**, minimum 50 frames per request (so ≥ $0.01).
- Muse Spark Standard is $1.25 in / $4.25 out / $0.15 cached-in per 1M tokens.
- Muse Spark Contributor is $0.10 / $0.20 / $0.002.
- Web search grounding is $2.50 per 1,000 queries (not used here).
- The Files API is not billed (the `files` row exists so uploads appear in the ledger at $0).
- There is no per-video-second price. Video is billed per frame: 10 s at 30 fps = 300 frames = **$0.06**.

## Briefing hints vs docs

| Hint | Verdict |
|---|---|
| SAM 3.1 ≈ $2.50 / 1,000 images | **Confirmed** |
| Spark ≈ $1.25 / $4.25 per 1M in/out | **Confirmed** for Standard mode (cached input $0.15) |
| ~50 images per request | **Confirmed for Muse Spark** (hard 400 above 50). **SAM takes one media part per request** |
| Video up to 15,000 frames / 16 objects | **Confirmed**: 15,000 frames per request, 16 tracked objects per frame, 16 prompted objects |
| Video uploaded as a file (batch), not streamed | **Partly**: the clip goes in as a URL, data URL or uploaded `file_id` (upload is synchronous, no job polling). The *response* can stream per frame over SSE |

## Live API checks (2026-11-02)

These are the first real calls from this harness, made on the synthetic `_placeholder` fixtures. They check the wire contract, not accuracy on real scenes. Raw response bodies are in `out/raw/`, and every call is in `ledger.csv`.

| Check | Result |
|---|---|
| SAM image response | Matches the grammar above: `<0f>0<\|box;x1=287;y1=406;x2=314;y2=433;w=1200;h=900;c=0.89\|><\|mask;x=0;y=0;c=0.89;data=28,28,~...\|>` |
| Box corners and mask size | `x2`/`y2` are inclusive. The mask's H×W equals the box size (28×28 for a 287–314 × 406–433 box) |
| Zero matches | Empty `output_text` with `status: completed`, and **still billed**: 1 image, or all 50 frames for video |
| SAM video | One line per frame (50 lines for 50 frames), `!` one_bit masks, one id (`0`) held across the clip |
| Mask encoding of an image box prompt | **`~` (lossless)** when `mask_encoding: "lossless"` is sent, so "box/point prompts always return one_bit" did not hold here. Video box prompts are untested |
| Object ids | Concept matches start at `0`. A box prompt's mask comes back under that prompt's object id (`1`) |
| Usage fields | `images_processed` and `video_frames_processed`; for Spark, `input_tokens`, `output_tokens` and `reasoning_tokens`, as documented |
| Files upload | Synchronous, 1.7 s for 7.8 KB. The next run reused the cached `file_id` |

Latency (single calls, so indicative only):
- SAM image: 367–1,012 ms. The first call of a run was the slow one.
- SAM video: 2.8–3.6 s for 50 frames at 640×360.
- Spark locate: 6.4 s at `effort: low` (1,503 input / 717 output tokens, 528 of them reasoning).

Accuracy (synthetic shapes, few samples):
- **SAM matches concepts literally.** "resistor" found nothing on tan bars and "orange ball" found nothing on a flat disc; "red circle" and "orange circle" found them at 0.89 and 0.95. An empty result costs the same as a hit, so check a concept on one image before a video run.
- **SAM masks are pixel-accurate on small objects.** A ~28 px dot gave a 629 px mask (true area ~615 px); a 41×16 bar gave 656 px (true 656).
- **Spark's y came back ~14% too large; x was accurate.**
  - On the 1200×900 image the dot's y was 464–498 px instead of 406–434, and the bars' 376–398 instead of 330–346. On the grid that is 534 vs 467 (dot) and 430 vs 375 (bars). x was within 17 px.
  - Two objects on one synthetic image are too few to call it systematic. Check on real photos with known positions before drawing Spark boxes as-is.

## NOT SUPPORTED per docs

- **Live / realtime camera or video-stream input** to SAM 3.1 or Muse Spark. The only realtime endpoint is Muse Voice Transcribe (`wss://api.meta.ai/v1/asr/realtime`, audio only). `meta_eval/live_probe.py` therefore sends single frames as images.
- Multiple concepts in one SAM request. Send one request per concept.
- Mixing a concept phrase with box/point prompts in one SAM request.
- Negative boxes. Only points can be negative.
- Mask output as PNG/polygon from the API. The client library converts it to COCO RLE or SVG path.
- SAM tuning knobs such as score thresholds or `max_masks`: not documented.
- Logprobs on Muse Spark.

## Decisions (made without asking; docs were clear enough)

1. **SAM is called non-streaming.**
   - Same output format per the docs, and one simpler code path.
   - Before parsing, the output is split into lines at each `<Nf>` marker. This is safe because the mask base85 alphabet excludes `<`, `>`, `,`, `;` and `|`.
   - Parsing uses the official `meta-sam-parser` (PyPI).
2. **`include_confidence: "true"` is sent on every SAM call.**
   - Image masks use `lossless`. Video masks use `one_bit` (smaller payload for many frames).
3. **`sam_image` prompt grouping**:
   - Each `--text` becomes its own request, because the API takes one concept per request. Each is billed as one image.
   - All `--point`/`--box` flags go in **one** extra request. Each flag is a separate object (ids 1..n).
4. **`sam_video` always re-encodes locally with ffmpeg before upload**:
   - First `--max-frames` frames, H.264 yuv420p, audio stripped, `+faststart`. The bytes sent are the bytes the overlay is drawn on, and the billed frames are capped locally.
   - Uploads set `expires_after` to 1 day so storage does not grow forever.
   - The `file_id` is cached in `out/<stem>/upload.json`, keyed by sha256, so a re-run does not re-upload.
5. **Spark uses the Responses API with `text.format` json_schema.**
   - `locate` wraps the list as `{"objects": [...]}`, because the strict subset requires an object root. The saved JSON is the plain list you asked for.
   - The schema comes from pydantic models, or from a JSON Schema file (`--schema path.json`).
   - `strict` is not sent; its default is unknown. Schemas are kept strict-compatible so it can be turned on later.
6. **Spark defaults**:
   - `muse-spark-1.3` (Standard: your images are not used for training).
   - `reasoning.effort = "low"`.
   - `max_output_tokens = 4000`. This caps worst-case output at about $0.017 per call.
   - `--model`, `--effort` and `--max-output-tokens` override these.
7. **`store: false` on every Responses call.**
   - No server-side persistence of your media, and it avoids the `store=true` 16 MB 413.
8. **Retries**:
   - 429/500/502/503 are retried at most twice, honouring `Retry-After` (capped at 60 s).
   - **504 is not retried**, because the docs say the same request will usually time out again.
   - Retries don't count against `MAX_CALLS_PER_RUN`, but each retry is noted in the ledger.
9. **Dry-run token estimate for Spark**:
   - About 1,500 tokens per 1280×960-pixel area, scaled by area (to a minimum of 3), plus 110 overhead, plus (prompt + schema JSON) chars ÷ 4.
   - Output is shown as both "typical" (800) and "max" (`max_output_tokens`).
   - These are rough. The ledger always records the real `usage`.
10. **File names**:
    - Overlays are named per tool (`sam_image_overlay.png`, `sam_video_overlay.mp4`, `spark_overlay.png`), so running SAM and Spark on the same image doesn't overwrite one overlay with the other.
11. **Every successful response body is saved** to `out/raw/<UTC timestamp>_<path>.json`.
    - A response the harness fails to parse can be debugged without paying for the call again.
    - Response bodies hold no key. `out/` is gitignored.
