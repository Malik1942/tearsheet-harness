You are analyzing ONE photograph that a designer saved because they liked how it looks.
You do not know what product it will be used for. Do not guess.

Your task is to explain what makes this image look the way it does, in four parts.

1. MEASUREMENTS. Statements you can read off the image. Use relative units only:
   ratios, fractions of the frame, counts, positions as "left third", "hugging the right edge".
   Never pixels, never font names unless the glyphs are unmistakable (then also describe them).
   Each measurement states how you measured it. Examples of good measurements:
   - "largest text height : smallest text height ≈ 9 : 1"
   - "about 55% of the frame is empty background"
   - "exactly one saturated hue (orange-red), covering ≈ 3% of the frame, used only on the date"
   - "all text is set flush to the left edge; the right 40% of the frame has no text"
   - "the headline is a heavy, wide, low-contrast sans with tight letterspacing; the body text is a light sans"
   If any text is visible, always include one measurement that describes the type: weight, width, stroke
   contrast, serif or sans, letterspacing. Describe it; do not name it.

2. HYPOTHESES. Your interpretation of why the arrangement works: hierarchy, rhythm, tension,
   emphasis, mood. Each hypothesis must list the measurement ids it rests on and a confidence
   from 0 to 1. A hypothesis with no supporting measurement is not allowed; lower confidence
   instead of inventing support.

3. TRANSFERABLE RELATIONS. At most three rules that would have to survive for a new design
   with different content to still feel like this image. Phrase each as a rule a layout engine
   could apply, and name the parameter it sets from this list:
   type_scale_ratio, hierarchy_mode, density, grouping, rhythm, alignment_edge,
   image_text_dominance, accent_placement, accent_coverage, palette_hue_count.
   If a rule fits none of these, set parameter to "none" and still write the rule.
   Point each rule at the hypothesis it comes from.

4. FRAGILE_IF_CHANGED. The single change that would most destroy this image's character,
   in one sentence.

Also return REGIONS: for each measurement, a box in 0–1000 normalized coordinates of the area
it refers to.

Rules: describe only what is visible; prefer fewer, more certain statements; no prose outside
the JSON; return strict JSON matching the schema.
