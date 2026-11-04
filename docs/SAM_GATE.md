# SAM gate (13_SAM_SPEC §6)

Run Tue 2026-11-03, 12:30 PST (20:30 UTC). Model `sam-3.1`, one concept prompt per call. Images went out at 2048 px on the long side: g2 and g1 at 2048×1365, IMG_6966 at 2048×1536.

Status: **PASS (2 of 3 photos). Malik's call, Tue 2026-11-03: build §7, with two limits.**

## Conclusion: build, with two limits

1. **Prompts are specific.** On g2, "the car" also masked the blurred second car in the lower-right foreground (IoU 0.69). That is a vague prompt, not a SAM failure: "the silver car in front" names one car. The product sends Spark's region label, which already names the thing ("hero car body", "red taillight accents"), never a generic noun.
2. **Masks only for clear, discrete objects.** g1's two failures and Chicago's "the stage" are the same class: a soft, out-of-focus mass, or a thin sliver lying on the ground. SAM is not good at either. The rule does not change: only sharp, separate objects get a mask. When no reliable mask comes back (confidence < 0.5 or IoU < 0.4), the Spark value stays and is labeled `estimated`.

## Method

- **Mask side:**
  - Take the union of every returned mask with confidence ≥ 0.5. A prompt such as "the red taillights" returns one mask per lamp.
  - Each mask raster comes at the model's reduced resolution. It is scaled to its box with nearest-neighbour.
  - Area share is the union's pixels over the frame's pixels.
  - The mask bbox is the union's bounding box, on the same 0–1000 grid as Spark's `box_1000`.
- **Spark side:** the `box_1000` of the region the prompt names.
  - g1 and g2 use the Monday gate extraction (`out/g1`, `out/g2`, prompt `extract_brick.md`, the original v1).
  - IMG_6966 uses a fresh extraction with `extract_brick_v3.md` at effort medium (`out/IMG_6966`).
- **IoU** is computed between the mask bbox and the Spark box.
- **Pass rule per prompt:** confidence ≥ 0.5 and IoU ≥ 0.4.
- **Pass rule per photo:** at least two prompts pass, and the eyeball check agrees.
- **Overall pass:** 2 of 3 photos.

## Results

| Photo | Prompt | Spark region | Masks (kept) | Confidence | Area share | Mask bbox | Spark box | IoU | Latency | Numbers |
|---|---|---|---|---|---|---|---|---|---|---|
| g2 | the car | hero car body | 2 (2) | 0.942, 0.852 | 46.8% | 125,141,1000,1000 | 110,138,865,850 | 0.686 | 2970 ms | pass |
| g2 | the red taillights | red taillight accents | 2 (2) | 0.965, 0.863 | 1.75% | 333,424,815,613 | 318,422,815,613 | 0.960 | 1707 ms | pass |
| g2 | the dark background | overall low-key field | 1 (1) | 0.750 | 20.6% | 441,0,1000,607 | 0,0,1000,1000 | 0.339 | 1499 ms | fail (IoU) |
| g1 | the blossoms | sharp blossom foreground mass | 0 | none | 0 | none | 0,0,790,998 | none | 809 ms | fail (no mask) |
| g1 | the tower | blurred background building and tower | 1 (1) | 0.511 | 9.5% | 870,28,1000,1000 | 555,20,1000,999 | 0.290 | 1437 ms | fail (IoU) |
| IMG_6966 | the lit sign | CHICAGO marquee letters | 1 (1) | 0.910 | 2.5% | 306,372,699,486 | 290,355,702,472 | 0.732 | 1340 ms | pass |
| IMG_6966 | the stage | inner trapezoidal bandstand | 1 (1) | 0.683 | 0.57% | 268,765,739,817 | 265,493,713,793 | 0.085 | 726 ms | fail (IoU) |
| IMG_6966 | the audience | foreground audience band | 32 (32) | 0.54–0.75 | 18.4% | 31,712,1000,1000 | 0,678,1000,1000 | 0.867 | 1694 ms | pass |

| Photo | Prompts passing on numbers | Photo verdict (numbers) |
|---|---|---|
| g2 | 2 of 3 (car, taillights) | pass |
| g1 | 0 of 2 | fail |
| IMG_6966 | 2 of 3 (lit sign, audience) | pass |

**Overall: 2 of 3 photos pass on the numbers.**

## What the overlays show (Malik confirms)

Red marks the SAM mask union and its bbox. Cyan marks the Spark region box.

- **g2, the car:** the car body is masked. A second mask covers the blurred car fragment in the lower-right foreground, so the union bbox runs to the frame's corner. It is still on "a car", but it is not only the hero car.
- **g2, the red taillights:** the mask sits tightly on the lamps. Its bbox nearly coincides with Spark's box.
- **g2, the dark background:** SAM masks only the upper-right dark field. Spark's "overall low-key field" is the whole frame. SAM segments things, not tonal fields.
- **g1, the blossoms:** no mask came back.
- **g1, the tower:** a low-confidence strip at the right edge (the spire). The blurred building is not covered.
- **IMG_6966, the lit sign:** the mask sits on the CHICAGO letters.
- **IMG_6966, the stage:** a thin sliver along the stage floor's front edge. The bandstand volume above it is not covered.
- **IMG_6966, the audience:** 32 head-and-shoulder masks across the foreground band.

**Pattern:** SAM is reliable on discrete, sharp objects: the sign letters, the taillights, the car body, the audience heads. It fails on diffuse or out-of-focus masses (the blossoms, the blurred tower) and on whole-frame tonal fields (the dark background). It is unreliable on concepts with no crisp edge (the stage). If the gate holds after the eyeball check, §7 should send only discrete-object regions to SAM and keep fields and soft masses on Spark and pixels. If the gate fails, README "next" says: "masks for diffuse and out-of-focus regions were missing or partial; discrete objects were tight."

## Variance

"The red taillights" on g2 ran twice with the same input bytes. The two runs returned identical values:

| Value | Run 1 | Run 2 |
|---|---|---|
| Area share | 0.0175 | 0.0175 |
| Confidences | 0.965, 0.863 | 0.965, 0.863 |
| Mask bbox | 333,424,815,613 | 333,424,815,613 |
| IoU | 0.960 | 0.960 |

The values are identical to four decimals, so the two-decimal requirement holds. Only the latency differed: 1707 ms, then 864 ms.

This repeats the SAM call, not the §2 product pipeline, which is not built yet. Every mask-derived value in that pipeline would come from these same masks.

## Latency and cost

- **Latency:** 726–2970 ms per call, median 1437 ms, over 9 recorded calls.
- **SAM cost:** 10 calls × $0.0025 = $0.025. The rate is the per-image rate in ENDPOINTS.md.
  - The 10 include one call ("the car", 20:30:46 UTC, 2691 ms). Its response was lost when the script crashed on the mask shape: the raster comes at reduced resolution and was not yet scaled to its box. The call was rerun after the fix.
- **Spark cost:** the IMG_6966 extraction (prompt v3, effort medium) cost $0.0172.
- **Gate total:** $0.0422.
- **Ledger after the gate:** 53 calls, $0.6274 of the $150 cap.

## Files

- **Results:** `out/sam_gate/sam_gate.json`
- **Overlays:**
  - `docs/overlays/sam_g2_car.png`, `sam_g2_red_taillights.png`, `sam_g2_red_taillights_run2.png`, `sam_g2_dark_background.png`
  - `sam_g1_blossoms.png`, `sam_g1_tower.png`
  - `sam_IMG_6966_lit_sign.png`, `sam_IMG_6966_stage.png`, `sam_IMG_6966_audience.png`
  - Contact sheet: `docs/overlays/sam_gate_contact.jpg`
  - Overlays and `out/` are derived from the probe photos. They stay local and are gitignored.
- **Script:** `scripts/sam_gate.py`. Preview with `.venv/bin/python scripts/sam_gate.py --dry-run`. A real run sends 9 SAM calls.
