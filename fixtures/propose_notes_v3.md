# Proposal notes v3: the v2 set with a designer's lean (sealed before run 3; never edited after)

Spec v3 §7: "Re-run the sealed v2 set once with a designer's lean and record the result, whatever it is." Same three intents, same expected picks and Not lines as v2 (`propose_notes_v2.md`, sha256 1796f8ff…), same scoring. New per intent: a `Lean:` line with the chips the designer set on the project, read BEFORE the call as request input (it becomes the prompt's lean paragraph; no chip word reaches the model), and nothing else of this file is read before the call. The picks and Not lines are read after, to score, as before.

Leans per spec v3 §7: concert log → dark, one accent; long-document reader → text-heavy, left-aligned; cycling computer → none.

Written and sealed by the harness session on 2026-11-02 evening PST, before the product's lean code exists; the prompt text the lean produces is the one the "Tearsheet 现状总结" session specified and will be re-verified byte for byte against the product before the run.

Scoring (as v1 and v2):

* Per intent: pass = at least 2 of the sealed picks come back (for an intent with only two sealed picks, both), and every quoted_rule validates against that brick's rules.
* Overall: pass = at least two of the three intents pass.
* A pick listed under "Not:" counts as a miss with a reason, even if the other two hit.

Brick ids: g1, g2, calmmouse, greencar, c1, bauhaus-1923-staatliches-bauhaus-weimar, haeckel-1904-trochilidae-plate-99, iran-1260s-star-cross-luster-tiles, matthews-19c-glyphography-trade-card, lissitzky-1923-dlya-golosa, secession-1902-beethoven-catalogue, jpl-2016-visions-mars

## Intent: A concert log for someone who goes to a lot of shows and wants to look back on a year
Lean: dark, one accent
Picks: g2, calmmouse, iran-1260s-star-cross-luster-tiles
Why: g2's accent rule ("saturated color to <5% red focal accent … all else neutral") is the accent discipline for a list: one hot mark per entry, on the show's name; its palette rule (silvery neutrals + black, darkness ~60%) gives the dark skin. calmmouse's type rule ("headline cap-height about 2x subcopy height with heavier weight and tighter spacing") is the entry hierarchy: show name over date · venue; its accent rule agrees with g2's. The tiles' rhythm rule ("alternate large ornate modules with smaller plain filler modules in an offset interlocking grid with no single center") is the Year review: a month grid where the shows that mattered sit as the large modules and the rest as filler, with no single hero.
Not: haeckel-1904-trochilidae-plate-99 (its density rule, coverage above 90% with no margins, is a plate, not a list; a log needs margins), jpl-2016-visions-mars (its type rule, title 9x the smallest text, is a poster anchor and would fight a list of equals).

## Intent: A reader for long documents such as contracts and papers, where the person keeps their place and marks passages
Lean: text-heavy, left-aligned
Picks: lissitzky-1923-dlya-golosa, matthews-19c-glyphography-trade-card, iran-1260s-star-cross-luster-tiles
Why: Lissitzky's palette rule ("one saturated hue plus black on light ground, using the hue only for the largest shape and thin accent lines covering <15% of area") is the reading surface: black text on light, the one hue reserved for marks as thin lines. Matthews' type rule ("display headline cap-height about 3x body text height while stepping down through spaced small-caps for middle lines") is document hierarchy: title, then section heads as spaced small caps, then body, which is how a reader keeps their place. The tiles' grouping rule ("each module as dense center covering ~75% with a thin continuous edge band under ~15% for secondary micro-detail") is the page: a dense text body with a thin margin band for the marks and notes. Expected conflict, wanted: Matthews' center axis against the left edge the shell sets; resolved to left by hand.
Not: haeckel-1904-trochilidae-plate-99 (coverage above 90%, no margins: nowhere to mark), jpl-2016-visions-mars (middle 60% image-only: a reader has no image slot).

## Intent: A cycling computer screen for glancing at speed, distance and heart rate mid-ride, in sunlight
Lean: none
Picks: jpl-2016-visions-mars, lissitzky-1923-dlya-golosa, calmmouse
Why: Mars' type rule ("display title cap-height about 9x the smallest supporting text to preserve anchor hierarchy") is the glance screen: speed huge, labels tiny, one number read in a second. Lissitzky's palette rule (one saturated hue plus black on light ground) is the sunlight skin: light field, black figures, one hue for the alert. calmmouse's accent rule ("restrict a single saturated accent hue to the bottom line only, covering under 5% of the frame") is the alert discipline: color on one line (the heart-rate zone), nowhere else. These three are also where the extracted rules leave little choice; greencar's hierarchy rule (primary subject at least 2x the next) is the only near swap for Mars. Note: v1 picked bauhaus for this intent from its description (white field); its extracted rules say a dark ground and identical cap-heights with no size hierarchy, the opposite of what a glance screen needs, so it moves to Not.
Not: bauhaus-1923-staatliches-bauhaus-weimar (1:1 cap-height forbids the size hierarchy; dark ground loses in sunlight), haeckel-1904-trochilidae-plate-99 (edge-to-edge density is the opposite of a glance screen).
