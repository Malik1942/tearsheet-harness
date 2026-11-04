# Proposal regression, run 3 (lean), 2026-11-03

**Setup**

- `NOTES=fixtures/propose_notes_v3.md OUT_DIR=out/propose_v3 scripts/propose.sh --send`
- muse-spark-1.3, effort low, the same prompt and schema as the product (`npm run check:prompts`: propose prompt 6b9984be… on both sides).
- Library: the 12 samples. Leans are taken from the sealed notes (`propose_notes_v3.md`, sealed before this run, never edited).
- One call per intent, no re-runs.

**Result: 1 of 3 intents pass.** The set passes at 2 of 3, so run 3 fails, the same score as run 2.

| Intent | Lean | Picks (quoted rule's parameter) | Sealed expect | Overlap | Verdict |
|---|---|---|---|---|---|
| Concert log, look back on a year | dark, one accent | g2 (accent_coverage), c1 (image_text_dominance), secession (rhythm) | g2, calmmouse, iran | g2 | MISS |
| Reader for long documents | text-heavy, left-aligned | bauhaus (alignment_edge), matthews (type_scale_ratio), calmmouse (image_text_dominance) | lissitzky, matthews, iran | matthews | MISS |
| Cycling computer in sunlight | none | jpl (type_scale_ratio), secession (palette_hue_count), calmmouse (accent_coverage) | jpl, lissitzky, calmmouse | jpl, calmmouse | PASS |

All nine quoted rules are verbatim; none was dropped.

**Did the lean show up in the picks?**
- Concert: g2 was quoted for its accent_coverage rule ("one accent"), and g2 and secession are two of the three ids that "dark" names.
- Reader: two of the three picks quote alignment, image-share or hierarchy rules ("text-heavy, left-aligned"). Bauhaus's justify-both rule is quoted under alignment_edge.

**Cost:** 3 calls, $0.0253 (latency 7.6–14.4 s). The ledger after the run: 56 calls, $0.6526 of $150.

**Shipping:** proposals stay **ON** under spec v3 P6 and Malik's verdict of 2026-11-02 21:35 ("开启，按 P9", quoted in PROPOSE_RUN_2026-11-02.md). P6 already records 1/3 designer agreement as the known limit, and lean chips as the product's answer to it. `PROPOSE_ENABLED=1` was set for production on 2026-11-03 at ~13:10 PST and took effect with deployment 1e4f6c0.
