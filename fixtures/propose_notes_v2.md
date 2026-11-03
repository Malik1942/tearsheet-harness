# Proposal notes v2, control set (sealed before run 2; never edited after)

Same three intents and the same scoring as `propose_notes.md` (v1). What changes: these picks are written from the bricks' **extracted rules** only (`bricks/src/fixtures/samples/*.json`, `transferable_relations`, the 36 one-sentence rules the proposer actually sees), not from the brick descriptions. v1 tested the proposer against relations the extraction never produced; v2 tests it against what it can quote. v1 stays sealed and is not replaced by this file.

Written by Claude (the harness session) on Malik's instruction, 2026-11-02 evening PT, after run 1. Disclosed: the author had seen run 1's picks. Mitigation: every pick below names the extracted rule it rests on; run 2 is three fresh calls, so the set also measures run-to-run consistency.

Scoring (as v1):

* Per intent: pass = at least 2 of the sealed picks come back (for an intent with only two sealed picks, both), and every quoted_rule validates against that brick's rules.
* Overall: pass = at least two of the three intents pass.
* A pick listed under "Not:" counts as a miss with a reason, even if the other two hit.

Brick ids: g1, g2, calmmouse, greencar, c1, bauhaus-1923-staatliches-bauhaus-weimar, haeckel-1904-trochilidae-plate-99, iran-1260s-star-cross-luster-tiles, matthews-19c-glyphography-trade-card, lissitzky-1923-dlya-golosa, secession-1902-beethoven-catalogue, jpl-2016-visions-mars

## Intent: A concert log for someone who goes to a lot of shows and wants to look back on a year
Picks: g2, calmmouse, iran-1260s-star-cross-luster-tiles
Why: g2's accent rule ("saturated color to <5% red focal accent … all else neutral") is the accent discipline for a list: one hot mark per entry, on the show's name; its palette rule (silvery neutrals + black, darkness ~60%) gives the dark skin. calmmouse's type rule ("headline cap-height about 2x subcopy height with heavier weight and tighter spacing") is the entry hierarchy: show name over date · venue; its accent rule agrees with g2's. The tiles' rhythm rule ("alternate large ornate modules with smaller plain filler modules in an offset interlocking grid with no single center") is the Year review: a month grid where the shows that mattered sit as the large modules and the rest as filler, with no single hero.
Not: haeckel-1904-trochilidae-plate-99 (its density rule, coverage above 90% with no margins, is a plate, not a list; a log needs margins), jpl-2016-visions-mars (its type rule, title 9x the smallest text, is a poster anchor and would fight a list of equals).

## Intent: A reader for long documents such as contracts and papers, where the person keeps their place and marks passages
Picks: lissitzky-1923-dlya-golosa, matthews-19c-glyphography-trade-card, iran-1260s-star-cross-luster-tiles
Why: Lissitzky's palette rule ("one saturated hue plus black on light ground, using the hue only for the largest shape and thin accent lines covering <15% of area") is the reading surface: black text on light, the one hue reserved for marks as thin lines. Matthews' type rule ("display headline cap-height about 3x body text height while stepping down through spaced small-caps for middle lines") is document hierarchy: title, then section heads as spaced small caps, then body, which is how a reader keeps their place. The tiles' grouping rule ("each module as dense center covering ~75% with a thin continuous edge band under ~15% for secondary micro-detail") is the page: a dense text body with a thin margin band for the marks and notes. Expected conflict, wanted: Matthews' center axis against the left edge the shell sets; resolved to left by hand.
Not: haeckel-1904-trochilidae-plate-99 (coverage above 90%, no margins: nowhere to mark), jpl-2016-visions-mars (middle 60% image-only: a reader has no image slot).

## Intent: A cycling computer screen for glancing at speed, distance and heart rate mid-ride, in sunlight
Picks: jpl-2016-visions-mars, lissitzky-1923-dlya-golosa, calmmouse
Why: Mars' type rule ("display title cap-height about 9x the smallest supporting text to preserve anchor hierarchy") is the glance screen: speed huge, labels tiny, one number read in a second. Lissitzky's palette rule (one saturated hue plus black on light ground) is the sunlight skin: light field, black figures, one hue for the alert. calmmouse's accent rule ("restrict a single saturated accent hue to the bottom line only, covering under 5% of the frame") is the alert discipline: color on one line (the heart-rate zone), nowhere else. These three are also where the extracted rules leave little choice; greencar's hierarchy rule (primary subject at least 2x the next) is the only near swap for Mars. Note: v1 picked bauhaus for this intent from its description (white field); its extracted rules say a dark ground and identical cap-heights with no size hierarchy, the opposite of what a glance screen needs, so it moves to Not.
Not: bauhaus-1923-staatliches-bauhaus-weimar (1:1 cap-height forbids the size hierarchy; dark ground loses in sunlight), haeckel-1904-trochilidae-plate-99 (edge-to-edge density is the opposite of a glance screen).
