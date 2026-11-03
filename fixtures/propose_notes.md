# Proposal notes (sealed before any proposal call; never edited after)

Three intents against the sample library. For each: the brick ids a designer would pick, and why. The model never sees this file. Only the heading line of each block is sent as the intent; the Picks line is read after the call, to score.

Scoring:

* Per intent: pass = at least 2 of the sealed picks come back (for an intent with only two sealed picks, both), and every quoted_rule validates against that brick's rules.
* Overall: pass = at least two of the three intents pass.
* A pick listed under "Not:" counts as a miss with a reason (subject match instead of relation match), even if the other two hit.
* These picks were written from the bricks' descriptions, not from their extraction outputs. Before scoring a miss against the proposer, open the brick: if the relation the Why relies on was never extracted, the miss belongs to extraction, not to proposal.

Brick ids: g1, g2, calmmouse, greencar, c1, bauhaus-1923-staatliches-bauhaus-weimar, haeckel-1904-trochilidae-plate-99, iran-1260s-star-cross-luster-tiles, matthews-19c-glyphography-trade-card, lissitzky-1923-dlya-golosa, secession-1902-beethoven-catalogue, jpl-2016-visions-mars

## Intent: A concert log for someone who goes to a lot of shows and wants to look back on a year
Picks: g2, lissitzky-1923-dlya-golosa, calmmouse
Why: g2 sets the skin and the accent discipline (near-black field, one hot accent only on the hero, which becomes the show's name). Lissitzky sets the left edge and the index rhythm (its thumb index becomes the month rail in Year review); its red agrees with g2's accent, so the two do not fight on palette. CalmMouse sets the three-level text hierarchy for date · venue · tags, accent only on the last line. Left unexpressed, knowingly: g2's one-sided light.
Not: jpl-2016-visions-mars. A concert is not a poster; its bottom-weighted display title is poster logic and would fight a list.

## Intent: A reader for long documents such as contracts and papers, where the person keeps their place and marks passages
Picks: matthews-19c-glyphography-trade-card, lissitzky-1923-dlya-golosa, secession-1902-beethoven-catalogue
Why: Matthews sets the ceiling: text is the whole surface, one hue, high density, so the shell gets no image slots. Lissitzky gives the hard left edge, the index rhythm (a section rail) and one red accent reserved for marks. The Secession catalogue gives book-scale hierarchy (modest type scale, ornament as section breaks) so the page stays calm over an hour of reading. One conflict expected and wanted: Matthews' center axis against Lissitzky's left edge; resolved to left.
Not: haeckel-1904-trochilidae-plate-99 (dense, but image-led), g1 (airy, wrong for sustained reading).

## Intent: A cycling computer screen for glancing at speed, distance and heart rate mid-ride, in sunlight
Picks: bauhaus-1923-staatliches-bauhaus-weimar, calmmouse
Why: Bauhaus sets scale and weight (letters fill the field; the numerals become the image) and the daylight skin: white field, black figures, two saturated hues as two data channels. CalmMouse sets the accent discipline (one accent on one line, the hero stat) and the left edge for labels. Sunlight means a light field; no dark mode. Two picks on purpose: nothing in the library encodes an equal-weight stat grid, and a third brick would be padding.
Not: iran-1260s-star-cross-luster-tiles (a photographed object group on gray with shadows, not an all-over repeat; the grid relation is not there to transfer), c1, g2 (dark fields lose in sunlight; dark car photos are a subject match for "cycling", not a relation match).
