# Propose: does the model pick the bricks a designer would pick?

PRD 08 §10.2, proposal set. One Muse Spark **text** call per intent against the sample library (12 bricks, 36 rules). The model sees the intent and each brick's rules with their parameter: never a photo, a measurement, a hypothesis, or these notes.

**Pass (per intent, from the sealed notes):** at least two of the sealed picks come back (both, when only two are sealed), every `quoted_rule` validates (it equals one of that brick's rules character for character), and no pick is one the notes list under `Not:` (a subject match instead of a relation match). **Overall:** at least two of the three intents pass. A pick that fails validation is dropped and reported, never repaired. Before scoring a miss against the proposer, open the brick: if the relation the notes rely on was never extracted, the miss belongs to extraction.

All commands run from `meta-eval/`.

## 1. Seal (no calls, no key)

Written before any proposal call is made, by Malik, and not edited afterwards.

1. **Notes.** `fixtures/propose_notes.md`, three intents. Format, one block per intent:

   ```markdown
   ## Intent: a one-page menu for a small bakery
   Picks: calmmouse, matthews-19c-glyphography-trade-card, secession-1902-beethoven-catalogue
   Why: one or two lines on why a designer would reach for these.
   ```

   The heading line is the exact intent sent (quotes inside it are turned into `”`, as the product does). `Picks:` lists brick ids from `../bricks/src/fixtures/samples/` (the file name without `.json`); an optional `Not:` line names bricks that must not be picked. Nothing below the heading is read before the call; after it, only the `Picks:` and `Not:` lines are read, to score.
2. **Seal it.**
   ```bash
   chmod 444 fixtures/propose_notes.md && shasum -a 256 fixtures/propose_notes.md > fixtures/propose_notes.sha256
   ```
3. **Prompt and schema.** `fixtures/prompts/propose.md` is the product's prompt (`bricks/src/lib/proposePrompt.ts`) with the two placeholders; `fixtures/schemas/propose.json` is the product's constrained schema (`PROPOSE_SCHEMA` in `bricks/src/lib/propose.ts`). The harness renders the prompt the way the product does (`JSON.stringify(library, null, 1)` ≡ `json.dumps(indent=1)`), verified byte for byte on 2026-11-02. Record the hashes:
   ```bash
   shasum -a 256 fixtures/prompts/propose.md fixtures/schemas/propose.json
   ```
4. **Dry-run.** `scripts/propose.sh`. Nothing is sent. Check: schema name `ProposeResult`, `reasoning.effort` low, `max_output_tokens` 4000, `store: false`, 12 bricks in the library block, and the estimate (about $0.006 typical, $0.02 worst per intent).

## 2. Run (three real calls; needs Malik's go in chat)

```bash
scripts/propose.sh --send
```

One call per `## Intent:` heading, in file order; the harness call guard caps a run at three. A second sealed set gets its own files: `NOTES=fixtures/propose_notes_v2.md OUT_DIR=out/propose_v2 scripts/propose.sh --send` (v2 = the control set written from the extracted rules, run 2026-11-02). Each result lands in `out/propose/<intent-slug>/propose.json` with the rendered prompt, the raw picks, the validated picks, the dropped ones with reasons, the call record, and `sealed: { expected, overlap, pass }`. The ledger gets one row per call (`script = propose`).

No re-runs after a miss: a second attempt on the same intent is a different experiment and is recorded as one.

## Lean (spec v3, run 3)

The product lets the designer lean a proposal with chips (dark, airy, one accent, text-heavy, big titles, left-aligned, two colors, grid) and an optional anchor brick. The prompt gets a third placeholder, `{{LEAN}}`, glued to the end of the "Do not pick the same brick twice." line; with no lean it is empty and the rendering is byte-identical to the lean-less prompt (checked 2026-11-02). Chips become parameter families in a "Lean." paragraph (no chip word reaches the model); `dark` becomes "Also prefer these bricks" with the ids whose rule text names a dark ground (on the samples: bauhaus, g2, secession); an anchor adds an "Anchor." paragraph, is never a valid pick, and caps the picks at two. In a sealed set the lean goes on a `Lean:` line right under the intent heading (`Lean: none` for no lean) and an optional `Anchor:` line; those two lines are the only part of the file read before the call. `fixtures/propose_notes_v3.md` is the v2 set with the spec v3 §7 leans: `NOTES=fixtures/propose_notes_v3.md OUT_DIR=out/propose_v3 scripts/propose.sh --send`.

## 3. Judge

Per intent: PASS when `sealed.pass` is true. The set passes when at least two of the three intents pass (sealed notes, 2026-11-02). Record the outcome in `docs/PROPOSE_RUN_<date>.md`, and in the product set `PROPOSE_ENABLED=1` on Vercel only after that.

## Cost

Three calls at effort low: about $0.02 typical, $0.06 worst case. Harness cap stays $150 (`ledger.csv`).
