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

---

# Run 2, 2026-11-02 19:15 PST: control set v2 (picks written from the extracted rules)

Malik's call after run 1: "修的是测试的弱点，不是功能" (fix the test's weakness, not the feature). `fixtures/propose_notes_v2.md` (sha256 1796f8ff247eb5a9f9a59324295f831dac03cee7997e40c1b9ebef74ecbe7bbe) keeps the three intents and the scoring, but its picks rest only on the 36 extracted rules the proposer sees. Written by the harness session after run 1 (disclosed in the file), sealed before run 2. v1 untouched. Prompt, schema, effort, library unchanged. Results in `out/propose_v2/<slug>/propose.json`.

## Calls

| Intent | Status | Latency | In / out tok | Cost |
|---|---|---|---|---|
| Concert log | completed | 4.0 s | 2020 / 717 | $0.0034 |
| Long-document reader | completed | 19.0 s | 2020 / 1726 | $0.0099 |
| Cycling computer | completed | 5.2 s | 2020 / 956 | $0.0045 |

Total $0.018 (both runs $0.039). All 9 quoted rules validated, 0 dropped.

## Picks against v2

**1. Concert log.** Sealed: g2, calmmouse, iran tiles; Not: haeckel, mars. Returned: c1 (photo dominant, tiny label), haeckel (edge-to-edge >90%), iran tiles (offset grid). Overlap 1 of 3, and haeckel is on the Not line. **MISS.**

**2. Long-document reader.** Sealed: lissitzky, matthews, iran tiles; Not: haeckel, mars. Returned: calmmouse (headline 2x body), c1 (desaturated grays + one warm hue for marks), g2 (<5% red accent for marks). Overlap 0 of 3. **MISS.**

**3. Cycling computer.** Sealed: mars, lissitzky, calmmouse; Not: bauhaus, haeckel. Returned: mars, lissitzky, calmmouse, same three as run 1, same quoted rules. Overlap 3 of 3. **PASS.**

Overall under v2: 1 of 3 intents. **FAIL** as sealed (needs 2).

## What two runs show together

| Intent | Run 1 | Run 2 | Stable? |
|---|---|---|---|
| Concert log | tiles, haeckel, bauhaus | c1, haeckel, tiles | tiles + haeckel both times |
| Reader | calmmouse, g2, tiles | calmmouse, c1, g2 | calmmouse + g2 both times |
| Cycling | mars, lissitzky, calmmouse | mars, lissitzky, calmmouse | identical |

The proposer is consistent: five of nine picks repeat across runs and the glance-screen set is identical. Its misses are not noise; they are a stable reading that differs from the designer's:
- For "a log of many shows", it treats the problem as **density and grid** (coverage, offset modules) and never reaches for the dark-skin accent discipline (g2) or the entry hierarchy (calmmouse).
- For "a reader where the person marks passages", it anchors on **marks**: a tiny saturated accent on a neutral field (g2, c1) and a headline ratio (calmmouse). It never quotes Lissitzky's "one hue plus black on light ground" or Matthews' "3x headline stepping through small caps", which are the reading-surface and document-hierarchy rules a designer would take.
- For a **glance screen** its reading and the designer's coincide exactly, twice.

Across six calls: 18 of 18 quoted rules verbatim, no subject matches (no "car" for cycling, no poster for the concert), three different parameters per answer. The honesty constraint holds; the judgment gap is on intents whose product is a list of many entries.

## Status

Propose stays off on Vercel (`PROPOSE_ENABLED` unset); the product picks by hand. Judgment on shipping it on is Malik's.

## Verdict (Malik, 2026-11-02 19:2x PST): "关闭上线"

Propose ships **off**. Both sealed sets fail as written (0 of 3, then 1 of 3 intents). `PROPOSE_ENABLED` stays unset on Vercel; `/api/propose` answers `enabled: false` and the product offers picking by hand. The code, the prompt, the schema and this record stay in place so a later run can be compared to these two. What would change the verdict: a proposer that returns the designer's dark-skin accent rule (g2) and entry hierarchy (calmmouse) for a many-entries list, and the reading-surface rule (Lissitzky's palette) for a reader, without losing the verbatim-quote discipline.
