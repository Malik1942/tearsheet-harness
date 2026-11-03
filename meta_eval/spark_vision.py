"""Muse Spark vision -> schema-constrained JSON with 0-1000 normalized coordinates, plus overlay.

    python -m meta_eval.spark_vision fixtures/images/x.jpg --task locate --labels "resistor,LED,Arduino board"
    python -m meta_eval.spark_vision IMG [IMG ...] --task describe-json --schema path/to/schema.json
    python -m meta_eval.spark_vision IMG --task describe-json --schema my_pkg.schemas:Scene

--schema takes a JSON Schema file or a pydantic model as module:Class. Any object in the result with a
"box_1000" list is drawn on the overlay (first image).
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import cv2
from pydantic import BaseModel, ConfigDict, Field

from . import costs, render
from .client import OUT, ApiError, Client, data_url, output_text

SCRIPT = "spark_vision"
DEFAULT_MODEL = "muse-spark-1.3"
MAX_IMAGES = 50
DESCRIBE_PROMPT = (
    "Describe this image as JSON that matches the provided schema. Report any coordinates on a "
    "normalized 0-1000 grid of the image as sent: x first, (0,0) top-left, (1000,1000) bottom-right."
)


class Located(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    box_1000: list[int] = Field(min_length=4, max_length=4, description="[x1, y1, x2, y2] on a 0-1000 grid")
    confidence: float = Field(ge=0, le=1)
    notes: str


class LocateResult(BaseModel):
    # Wraps the list because structured-output schemas need an object root. (No docstring:
    # pydantic would send it to the model as the schema description.)
    model_config = ConfigDict(extra="forbid")
    objects: list[Located]


def locate_prompt(labels: list[str]) -> str:
    names = ", ".join(f'"{label}"' for label in labels)
    return (
        f"You are an object grounding expert. Provide the bounding box of every instance of these objects "
        f"in the image: {names}. Ensure the objects accurately match the request and do not miss any objects. "
        "For each instance give: label (exactly one of the names above), box_1000 as [x_min, y_min, x_max, y_max] "
        "on a normalized 0-1000 grid with (0,0) at the top-left, confidence from 0 to 1, and short notes. "
        "If you cannot find an object, omit it."
    )


def spark_request(*, model: str, prompt: str, image_urls: list[str], schema_name: str, schema: dict[str, Any],
                  effort: str, max_output_tokens: int) -> dict[str, Any]:
    content = [{"type": "input_text", "text": prompt}] + [{"type": "input_image", "image_url": u} for u in image_urls]
    return {
        "model": model,
        "input": [{"type": "message", "role": "user", "content": content}],
        "text": {"format": {"type": "json_schema", "name": schema_name, "schema": schema}},
        "reasoning": {"effort": effort},
        "max_output_tokens": max_output_tokens,
        "store": False,
    }


def box_to_pixels(box_1000: list[float], size: tuple[int, int]) -> render.Box:
    """0-1000 grid -> pixels of the image sent; clamps the slight overshoot the docs warn about."""
    width, height = size
    x1, y1, x2, y2 = (min(max(v, 0), 1000) for v in box_1000)
    return (x1 * width / 1000, y1 * height / 1000, x2 * width / 1000, y2 * height / 1000)


def find_boxes(value: Any) -> list[tuple[str, list[float], float | None]]:
    """Every (label, box_1000, confidence) found anywhere in a JSON value."""
    if isinstance(value, list):
        return [found for item in value for found in find_boxes(item)]
    if not isinstance(value, dict):
        return []
    found = [found for item in value.values() for found in find_boxes(item)]
    box = value.get("box_1000")
    if isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) for v in box):
        label = str(value.get("label") or value.get("name") or value.get("id") or "object")
        found.insert(0, (label, box, value.get("confidence")))
    return found


def load_schema(spec: str) -> tuple[str, dict[str, Any], type[BaseModel] | None]:
    """(name, JSON schema, pydantic class or None) from a .json path or module:Class."""
    if spec.endswith(".json"):
        schema = json.loads(Path(spec).read_text())
        name, model = schema.get("title", "Result"), None
    else:
        module_name, _, class_name = spec.partition(":")
        model = getattr(importlib.import_module(module_name), class_name)
        name, schema = model.__name__, model.model_json_schema()
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)[:64], schema, model


def parse_result(text: str, task: str, model: type[BaseModel] | None) -> Any:
    if task == "locate":
        return [obj.model_dump() for obj in LocateResult.model_validate_json(text).objects]
    return model.model_validate_json(text).model_dump() if model else json.loads(text)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m meta_eval.spark_vision", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("images", type=Path, nargs="+")
    parser.add_argument("--task", choices=["locate", "describe-json"], default="locate")
    parser.add_argument("--labels", help="comma-separated object names (locate)")
    parser.add_argument("--schema", help="JSON Schema file or module:PydanticClass (describe-json)")
    parser.add_argument("--prompt", default=DESCRIBE_PROMPT, help="instruction for describe-json")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--effort", default="low", choices=["minimal", "low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--max-output-tokens", type=int, default=4000, help="caps reasoning + output tokens")
    parser.add_argument("--max-side", type=int, default=1280, help="downscale long side before sending (0 = native)")
    parser.add_argument("--dry-run", action="store_true", help="print the request and cost; send nothing")
    args = parser.parse_args(argv)
    if args.task == "locate" and (not args.labels or len(args.images) != 1):
        parser.error("locate needs --labels and exactly one image")
    if args.task == "describe-json" and not args.schema:
        parser.error("describe-json needs --schema")
    if args.task == "describe-json" and not args.prompt.strip():
        parser.error("describe-json needs a non-empty --prompt")
    if len(args.images) > MAX_IMAGES:
        parser.error(f"at most {MAX_IMAGES} images per request")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    originals = [render.load_image(p) for p in args.images]
    sent = [render.fit(image, args.max_side) for image in originals]
    encoded = [render.encode(image, as_png=path.suffix.lower() == ".png")
               for image, path in zip(sent, args.images, strict=True)]

    if args.task == "locate":
        labels = [label.strip() for label in args.labels.split(",") if label.strip()]
        prompt, schema_name, model = locate_prompt(labels), "LocateResult", None
        schema = LocateResult.model_json_schema()
    else:
        prompt = args.prompt
        schema_name, schema, model = load_schema(args.schema)
    request = spark_request(model=args.model, prompt=prompt, image_urls=[data_url(raw, mime) for raw, mime in encoded],
                            schema_name=schema_name, schema=schema, effort=args.effort,
                            max_output_tokens=args.max_output_tokens)

    client = Client(dry_run=args.dry_run)
    client.reserve(1)
    sizes = [image.size for image in sent]
    typical, worst = costs.estimate_spark(sizes, len(prompt) + len(json.dumps(schema)), args.max_output_tokens)
    print(f"1 request to {args.model}; {len(sent)} image(s) sent at "
          f"{', '.join(f'{w}x{h}' for w, h in sizes)} ({sum(len(raw) for raw, _ in encoded):,} bytes)")
    costs.print_estimate(args.model, typical, worst)
    if not args.dry_run:
        costs.check_budget(costs.cost_usd(args.model, worst))

    try:
        result = client.post_json("/responses", request)
    except ApiError as error:
        print(f"API error: {error}", file=sys.stderr)
        raise SystemExit(4 if 400 <= error.status < 500 else 5) from None  # gate.sh stops everything on 4
    if result is None:
        return
    usage = costs.Usage.from_response(result.body)
    status = result.body.get("status", "")
    notes = f"task={args.task}; effort={args.effort}" + ("" if status == "completed" else f"; status={status}")
    summary = args.labels if args.task == "locate" else f"schema {schema_name}"
    call = costs.record_call(script=SCRIPT, model=args.model, input_file=",".join(map(str, args.images)),
                             prompt_summary=summary, result=result, usage=usage, images_sent=len(sent), notes=notes)

    text = output_text(result.body)
    out_dir = OUT / args.images[0].stem
    out_dir.mkdir(parents=True, exist_ok=True)
    # The exact bytes sent: any box_1000 in the result refers to this image, not to the original file.
    sent_name = "sent.png" if encoded[0][1] == "image/png" else "sent.jpg"
    (out_dir / sent_name).write_bytes(encoded[0][0])
    report: dict[str, Any] = {
        "script": SCRIPT, "task": args.task, "model": args.model, "effort": args.effort, "status": status,
        "images": [str(p) for p in args.images], "sent_sizes": [list(s) for s in sizes],
        "original_sizes": [list(image.size) for image in originals], "prompt": prompt, "schema_name": schema_name,
        "call": call.as_dict(),
    }
    try:
        report["result"] = parse_result(text, args.task, model)
    except ValueError as error:  # json.JSONDecodeError and pydantic.ValidationError are ValueErrors
        report["raw_text"] = text
        report["response_body"] = result.body  # full API response, so a billed call that failed to parse stays diagnosable
        (out_dir / "spark_vision.json").write_text(json.dumps(report, indent=2))
        print(f"could not parse model output ({status}): {error}", file=sys.stderr)
        raise SystemExit(3) from None  # unparsed; gate.sh continues with the next photo

    shapes = []
    for label, box, confidence in find_boxes(report["result"]):
        shapes.append(render.Shape(label, box_to_pixels(box, sizes[0]), confidence))
    if args.task == "locate":
        for obj, shape in zip(report["result"], shapes, strict=True):
            left, top, right, bottom = shape.box
            obj["box_px_sent"] = [round(left), round(top), round(right), round(bottom)]
    (out_dir / "spark_vision.json").write_text(json.dumps(report, indent=2))
    cv2.imwrite(str(out_dir / "spark_overlay.png"), render.draw(render.to_bgr(sent[0]), shapes))
    print(f"    -> {len(shapes)} box(es); wrote {out_dir / 'spark_vision.json'}, {out_dir / sent_name} and {out_dir / 'spark_overlay.png'}")


if __name__ == "__main__":
    main()
