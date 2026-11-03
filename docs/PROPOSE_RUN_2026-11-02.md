# Proposal run, 2026-11-02 (evening, PT)

Three real Muse Spark text calls, one per sealed intent, after Malik's go in chat. Prompt `fixtures/prompts/propose.md` (sha256 11156a48…), schema `fixtures/schemas/propose.json` (7a0a3831…), notes `fixtures/propose_notes.md` sealed before the run (1784cae3…). Library: the 12 sample bricks, 36 rules, as the product sends them. Effort low, `max_output_tokens` 4000, `store: false`. Results in `out/propose/<slug>/propose.json`; ledger rows `script = propose`.

## Calls

| Intent | Status | Latency | In / out / reasoning tok | Cost |
|---|---|---|---|---|
| Concert log | completed | 7.7 s | 2020 / 1347 / 1116 | $0.0083 |
| Long-document reader | completed | 6.5 s | 2020 / 961 / 774 | $0.0066 |
| Cycling computer | completed | 22.7 s | 2020 / 928 / 705 | $0.0065 |

Total $0.021. Every response parsed; all 9 quoted rules validated character for character (0 dropped). No pick came from a `Not:` line.

## Picks against the seal

**1. Concert log.** Sealed: g2, lissitzky, calmmouse. Returned: iran tiles ("offset interlocking grid with no single center" → equal entries for a year review), haeckel ("edge-to-edge coverage above 90%" → a dense look-back), bauhaus ("identical cap-height, hierarchy by ink color" → equal entries, color separates date/venue/notes). Overlap 0 of 3. **MISS.**

**2. Long-document reader.** Sealed: matthews, lissitzky, secession. Returned: calmmouse ("headline 2x subcopy" → keep one's place), g2 ("saturated color <5% focal accent" → marks without overwhelming text), iran tiles ("light neutral ground, no saturated accent" → comfortable long reading). Overlap 0 of 3. **MISS.**

**3. Cycling computer in sunlight.** Sealed: bauhaus, calmmouse (both required). Returned: mars ("display title 9x smallest text" → speed huge, labels tiny), lissitzky ("one saturated hue plus black on light ground" → readable in sunlight), calmmouse ("single accent on the bottom line under 5%" → one alert line). Overlap 1 of 2. **MISS.**

Strict sealed rule (≥2 intents pass): **0 of 3, FAIL** as written.

## Attribution (the seal's own clause: a miss whose Why relies on a relation that was never extracted belongs to extraction)

Checked against the rules the model actually saw (the bricks' extracted `transferable_relations`):

| Sealed pick | Relation the Why relies on | In the extracted rules? |
|---|---|---|
| g2 (intent 1) | dark field, one hot accent on the hero | yes: accent <5% red, darkness ~60% |
| calmmouse (1, 3) | three-level text hierarchy, accent only on the last line | yes: headline 2x subcopy, single accent on the bottom line |
| lissitzky (1, 2) | hard left edge, index rhythm (thumb index) | **no**: its rules are one hue + black on light ground, 15–25° rotation, overlapping forms |
| matthews (2) | text is the whole surface, one hue, high density | **no**: its rules center everything on a midline and put a vignette image in the middle third |
| secession (2) | book-scale hierarchy, ornament as section breaks | **no**: its rules are two flat values, a linking curve, one bordered image >70% of height (image-led) |
| bauhaus (3) | letters fill the field; white field, black figures, two hues | **partly**: 1:1 cap-height and justify-to-both-edges are there; the ground is extracted as **dark**, two inks |

So: intent 2 is an extraction miss on all three sealed picks (the proposer could not have quoted the relations the notes rely on). Intent 3 is half extraction (bauhaus's daylight skin is contradicted by its rules) and the proposer did return calmmouse. Intent 1 is the clean proposer miss: g2 and calmmouse were available with the right rules and were not picked; the model chose grid/density/equal-size rules instead, reading "log of many shows" as a density problem rather than a skin-and-hierarchy one.

What the proposer did consistently: every reason is a real rule, quoted exactly; it preferred different parameters across its three picks (as the prompt asks); its picks are relation matches, not subject matches (no "car" for cycling, no poster for concert). Its blind spot in this run is palette-and-accent discipline for a dark skin (g2) and the left-edge/index rhythm, which the library does not encode as rules at all.

## Not changed by this run

Prompt v3, the propose prompt and schema, the sealed notes. No re-runs. `PROPOSE_ENABLED` stays unset on Vercel; the product falls back to picking by hand.

## Judgment

Left to Malik, as with the gate. Options the record supports: (a) FAIL as sealed, ship Propose off; (b) PASS on attribution, since two of the three misses rest on relations the extraction never produced, and ship Propose on with the hand-pick fallback; (c) a second sealed set written from the extracted rules rather than from the brick descriptions, three more calls (~$0.02).
