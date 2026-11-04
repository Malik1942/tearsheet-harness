# Fair comparison (spec v3 §9), 2026-11-03

**Same task, two ways, one call each.**

- **Photos:** the twelve sample photos plus `IMG_6966` (the CHICAGO marquee, Malik's camera roll, taken 2025-12-27).
- **Intent:** "a concert log for someone who goes to a lot of shows".

## General chat

- **Model:** `muse-spark-1.3`, effort low: the same model and effort as Tearsheet's proposer.
- **Request:** one user message with the 13 photos attached at 1280 px on the long side, in a seeded random order (seed 20261103). No system prompt, no schema, no ids, no rules.
- **Script:** `scripts/fair_chat.py` (copy kept with this record). Raw answer in `out/fair_chat/answer.md`.
- **Call:** 15.5 s, $0.0290, in the ledger as `fair_chat`.

Prompt, verbatim:

> I'm making a concert log for someone who goes to a lot of shows. Here are 13 photos I saved because I liked how they look. Which ones should I use as references for the design?

| Photo | Brick |
|---|---|
| 1 | `greencar` |
| 2 | `IMG_6966` |
| 3 | `jpl-2016-visions-mars` |
| 4 | `haeckel-1904-trochilidae-plate-99` |
| 5 | `iran-1260s-star-cross-luster-tiles` |
| 6 | `g2` |
| 7 | `bauhaus-1923-staatliches-bauhaus-weimar` |
| 8 | `lissitzky-1923-dlya-golosa` |
| 9 | `g1` |
| 10 | `matthews-19c-glyphography-trade-card` |
| 11 | `secession-1902-beethoven-catalogue` |
| 12 | `calmmouse` |
| 13 | `c1` |

Answer, verbatim:

For a **concert log** — someone logging lots of live shows — you don't want car photos or nature photos, you want **poster / stage / editorial design** references.

Here's what you have, in order:

1. **Green BMW M4 + blue BMW** - car meet photo
2. **CHICAGO on stage** - musical from the audience
3. **NASA "Visit MARS"** - retro-futurist travel poster
4. **Hummingbirds** - Ernst Haeckel natural history plate
5. **Islamic star-and-cross tiles** - museum object photo
6. **Silver RWB Porsche convertible** - car show display
7. **STAATLICHES BAUHAUS IN WEIMAR 1919-1923** - book cover with big block type
8. **Red/black abstract with P and E shapes** - Russian Constructivist-style book page
9. **Cherry blossoms** - shallow-focus nature photo
10. **SPECIMEN OF GLYPHOGRAPHY** - Victorian title page with engraved vignette
11. **Woman holding skull** - Ernst Stöhr woodcut, black-and-white
12. **CalmMouse** - minimal modern web hero
13. **Old dark grey BMW 6-series** - car meet photo

### Use these for the design:

**2. CHICAGO - for *content* reference, not style**
This is the only actual live-performance photo. It's perfect to show what a log entry needs to capture: show title, stage, band/orchestra, lighting, crowd POV, date/venue feeling. Use it to decide your entry structure.

**3. MARS poster, 7. BAUHAUS cover, 8. Constructivist page - for *poster* reference**
These are the three best design references for a music person:
* Big, loud display type that can be read across a room — exactly what gig posters do
* Limited, high-contrast palette: red/yellow/black, orange/grey/brown, red/black/white
* Modular, geometric layout that works well for a repeatable log template: header title, subhead info, footer details

If you like bold, collectible-looking logs, start here.

**10. GLYPHOGRAPHY specimen and 11. Stöhr woodcut - for *print* reference**
If you want the log to feel like a zine / tour diary / keepsake book:
* 10 shows classic centered title-page hierarchy, serif mix, lots of white space
* 11 shows high-contrast illustration that photocopies well and looks punk/DIY next to setlists

You could use these for section dividers, cover page, and how to mix illustration + text.

### Skip these for this project:

1, 6, 13 - all cars. Great photos, but wrong subject and no useful type/layout for a show log.

4, 5, 9 - hummingbirds, tiles, blossoms. Beautiful detailed / texture references, but they'll fight with concert info and make the log hard to scan.

12 - CalmMouse. Too clean-corporate SaaS for a concert log — unless the person specifically wants an ultra-minimal app-style log.

**In short:** Build the system off **3 + 7 + 8** for poster energy, steal the page structure ideas from **10 + 11**, and use **2** pinned to the top of your moodboard to remind you what you're logging.

## Tearsheet

The live proposal on the public site (deployment 1e4f6c0):

- **Request:** the same intent, lean `dark` + `one accent`, and a library of the 12 starters plus `b_img6966`, the harness extraction of IMG_6966.
- **Path:** the real Projects page, in a fresh headless browser. The model saw rules only, never photos.
- **Call:** 12.5 s, $0.0098, through the product key (so not in the harness ledger).

| Pick | Quoted rule (verbatim) | Why (model) |
|---|---|---|
| b_img6966 | restrict the single warm accent to under 10% of frame and apply it only to title plus nested framing lines against a dark field | A dark log with a tiny warm title accent reads like a venue at night and makes each show title easy to scan. |
| g2 | Restrict saturated color to <5% red focal accent plus <10% distant cool background accent, all else neutral. | Keeping pages mostly neutral with a tiny red accent lets repeated photos and ticket stubs stand out without cluttering the log. |
| secession-1902-beethoven-catalogue | let one bordered image occupy >70% of height and reduce text to a single small centered line below the border | A big photo with one small caption line fits a repeated concert entry of image plus date and venue. |

No pick was dropped.

## Judged

| | General chat | Tearsheet |
|---|---|---|
| Surfaced the photo we hadn't thought of (CHICAGO) | yes, as "*content* reference, not style" | yes, first pick, for its accent rule |
| Reason lands on a screen element | partly: "header title, subhead info, footer details" for a template it does not show | yes: accent_coverage, and the photo's title rule moves both screens' titles |
| We kept the change | no screen changed | yes: the title-led layout is the video's main shot |

**Limits:** this is one sample each. The "general chat" here is the API with a plain message, not a consumer chat app.
