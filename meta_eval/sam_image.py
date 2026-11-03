"""SAM 3.1 on one image with concept (text), point and box prompts -> masks, boxes, scores, overlay.

    python -m meta_eval.sam_image fixtures/images/x.jpg --text "electrical cord" --text "rug edge" \
        [--point x,y] [--box x1,y1,x2,y2] [--max-side N] [--dry-run]

Each --text is its own request (one concept per request, billed as one image each). All --point and
--box prompts share one extra request; each flag is a separate object. Coordinates are pixels of the
upright original image; box corners are inclusive.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from meta_sam_parser import (
    CompletedOutcome,
    FramePrompt,
    PromptBox,
    PromptObject,
    PromptPoint,
    SegmentationMask,
    SegmentationMaskRecord,
    build_object_prompt,
    decode_mask_to_raster,
    decode_mask_to_rle,
    image_segmentation_format,
    video_segmentation_format,
)

from . import costs, render
from .client import OUT, Client, data_url, output_text

MODEL = "sam-3.1"
SCRIPT = "sam_image"
_FRAME_MARKER = re.compile(r"(?<!\n)(?=<\d+f>)")  # safe: '<' is not in the mask base85 alphabet


@dataclass(frozen=True)
class SamObject:
    frame: int
    object_id: str
    box: render.Box  # half-open, source pixels of the media sent
    confidence: float | None
    mask: np.ndarray  # bool raster spanning `box`
    encoded_mask: SegmentationMask

    def shape(self, label: str, scale: float = 1.0) -> render.Shape:
        shape = render.Shape(label, self.box, self.confidence, self.mask, key=f"{label}:{self.object_id}")
        return shape.scaled(scale)

    def summary(self, with_rle: bool = True) -> dict[str, Any]:
        left, top, right, bottom = self.box
        out: dict[str, Any] = {
            "object_id": self.object_id,
            "box_xyxy": [left, top, right - 1, bottom - 1],  # inclusive, as on the wire
            "confidence": self.confidence,
            "mask_area_px": int(self.mask.sum()),
        }
        if with_rle:
            rle = decode_mask_to_rle(self.encoded_mask)
            out["mask_rle_box_local"] = {"size": list(rle.size), "counts": rle.counts}
        return out


def sam_request(prompt_text: str, media_part: dict[str, str], *, mask_encoding: str = "lossless") -> dict[str, Any]:
    return {
        "model": MODEL,
        "input": [{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": prompt_text},
            media_part,
        ]}],
        "metadata": {"include_confidence": "true", "mask_encoding": mask_encoding},
        "store": False,
    }


def image_part(url: str) -> dict[str, str]:
    return {"type": "input_image", "image_url": url}


def object_prompt(
    size: tuple[int, int], boxes: list[tuple[int, ...]], points: list[tuple[int, ...]]
) -> tuple[str, dict[str, str]]:
    """Box/point prompt text for frame 0, plus the label for each object id."""
    objects, labels = [], {}
    for x1, y1, x2, y2 in boxes:
        object_id = len(objects) + 1
        box = PromptBox(x1, y1, x2 + 1, y2 + 1)  # the builder takes half-open boxes
        objects.append(PromptObject(id=object_id, prompts=[FramePrompt(frame=0, box=box)]))
        labels[str(object_id)] = f"box#{object_id}"
    for x, y in points:
        object_id = len(objects) + 1
        objects.append(PromptObject(id=object_id, prompts=[FramePrompt(frame=0, points=[PromptPoint(x, y)])]))
        labels[str(object_id)] = f"point#{object_id}"
    return build_object_prompt(size=size, objects=objects), labels


def parse_objects(body: dict[str, Any], media: str = "image") -> list[SamObject]:
    """Parse SAM special-token output (one line per frame) into decoded objects."""
    text = _FRAME_MARKER.sub("\n", output_text(body)).strip()
    parser = (image_segmentation_format() if media == "image" else video_segmentation_format()).create_parser()
    parser.push(text + "\n", emit=False)
    result = parser.finish(CompletedOutcome()).result
    for diag in result.diagnostics:
        print(f"  parser {diag.severity}: {diag.code}: {diag.message}")
    objects = []
    for record in result.records:
        if not isinstance(record, SegmentationMaskRecord):
            continue
        raster = np.frombuffer(decode_mask_to_raster(record.mask), np.uint8)
        b = record.bounds
        objects.append(SamObject(
            frame=record.frame.frame_index if record.frame else 0,
            object_id=record.object_id,
            box=(b.left, b.top, b.right, b.bottom),
            confidence=record.confidence,
            mask=raster.reshape(record.mask.height, record.mask.width).astype(bool),
            encoded_mask=record.mask,
        ))
    return objects


def _ints(count: int):
    def parse(value: str) -> tuple[int, ...]:
        parts = value.split(",")
        if len(parts) != count:
            raise argparse.ArgumentTypeError(f"expected {count} comma-separated numbers, got {value!r}")
        return tuple(int(float(p)) for p in parts)
    return parse


def _scale_coords(coords: tuple[int, ...], scale: float, size: tuple[int, int]) -> tuple[int, ...]:
    """Map original-image pixels to sent-image pixels: scale, round down, keep inside the media."""
    limits = size * (len(coords) // 2)
    return tuple(min(int(v * scale), limit - 1) for v, limit in zip(coords, limits, strict=True))


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m meta_eval.sam_image", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", type=Path)
    parser.add_argument("--text", action="append", default=[], help="concept prompt; repeatable, one request each")
    parser.add_argument("--point", action="append", default=[], type=_ints(2), metavar="X,Y")
    parser.add_argument("--box", action="append", default=[], type=_ints(4), metavar="X1,Y1,X2,Y2")
    parser.add_argument("--max-side", type=int, default=0, help="downscale long side before sending (0 = native)")
    parser.add_argument("--dry-run", action="store_true", help="print requests and cost; send nothing")
    args = parser.parse_args(argv)
    if not (args.text or args.point or args.box):
        parser.error("give at least one --text, --point or --box")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    original = render.load_image(args.image)
    sent = render.fit(original, args.max_side)
    scale = sent.width / original.width
    raw, mime = render.encode(sent, as_png=args.image.suffix.lower() == ".png")
    url = data_url(raw, mime)

    jobs = [(text, text, {}) for text in args.text]  # (summary, prompt text, object-id labels)
    if args.box or args.point:
        boxes = [_scale_coords(b, scale, sent.size) for b in args.box]
        points = [_scale_coords(p, scale, sent.size) for p in args.point]
        prompt, labels = object_prompt(sent.size, boxes, points)
        jobs.append((", ".join(labels.values()), prompt, labels))

    client = Client(dry_run=args.dry_run)
    client.reserve(len(jobs))
    planned = costs.Usage(images=len(jobs))
    print(f"{len(jobs)} request(s) to {MODEL}; image sent at {sent.width}x{sent.height} ({len(raw):,} bytes)")
    costs.print_estimate(MODEL, planned)
    if not args.dry_run:
        costs.check_budget(costs.cost_usd(MODEL, planned))

    shapes, results = [], []
    for summary, prompt, labels in jobs:
        result = client.post_json("/responses", sam_request(prompt, image_part(url)))
        if result is None:
            continue
        usage = costs.Usage.from_response(result.body)
        call = costs.record_call(script=SCRIPT, model=MODEL, input_file=str(args.image), prompt_summary=summary,
                                 result=result, usage=usage, images_sent=1)
        objects = parse_objects(result.body)
        scores = ", ".join(f"{o.confidence:.2f}" if o.confidence is not None else "?" for o in objects)
        print(f"    -> {len(objects)} mask(s) for {summary!r} [{scores}]")
        shapes += [o.shape(labels.get(o.object_id, summary)) for o in objects]
        results.append({"prompt": summary, "prompt_text": prompt, "call": call.as_dict(), "n_masks": len(objects),
                        "objects": [o.summary() for o in objects]})
    if args.dry_run:
        return

    out_dir = OUT / args.image.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "script": SCRIPT, "model": MODEL, "image": str(args.image),
        "original_size": list(original.size), "sent_size": list(sent.size), "sent_over_original": scale,
        "requests": results, "total_cost_usd": sum(r["call"]["cost_usd"] for r in results),
    }
    (out_dir / "sam_image.json").write_text(json.dumps(report, indent=2))
    cv2.imwrite(str(out_dir / "sam_image_overlay.png"), render.draw(render.to_bgr(sent), shapes))
    print(f"wrote {out_dir / 'sam_image.json'} and {out_dir / 'sam_image_overlay.png'}")


if __name__ == "__main__":
    main()
