"""Near-real-time webcam probe: single frames -> SAM 3.1 or Muse Spark, last result drawn on the live feed.

    python -m meta_eval.live_probe --backend sam --text "resistor" [--every N] [--max-calls 10] [--track] [--dry-run]
    python -m meta_eval.live_probe --backend spark --labels "resistor,LED"

The API has no live video input (docs/ENDPOINTS.md), so every update is one image request. SPACE sends
the current frame (default, --on-key); --every N sends one every N >= 2 seconds. At most one request is
in flight and --max-calls hard-caps the session. q or ESC quits. --source takes a camera index or a
video file (handy for repeatable runs).
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field, replace
from typing import Any, NamedTuple

import cv2
import numpy as np

from . import costs, render, sam_image, spark_vision
from .client import OUT, ApiResult, Client, data_url, output_text

SCRIPT = "live_probe"
SEND_MAX_SIDE = 1280
JPEG_QUALITY = 90
MIN_INTERVAL_S = 2.0
DRIFT_IOU = 0.5
WINDOW = "live_probe  (SPACE send, q quit)"
SPACE, ESC = 32, 27

Tracker = tuple[Any, render.Shape]  # (cv2 CSRT tracker, last tracked shape)


@dataclass
class Pending:
    future: Future[tuple[ApiResult | None, float]]
    frame: np.ndarray  # display frame at capture, for tracker re-init
    t_capture: float
    t_sent: float
    sent_size: tuple[int, int]
    payload_bytes: int
    tracked_at_capture: list[render.Shape]


class Completed(NamedTuple):
    pending: Pending
    t_response: float
    drifts: int


@dataclass
class Stats:
    total_ms: list[float] = field(default_factory=list)
    roundtrip_ms: list[float] = field(default_factory=list)
    cost_usd: float = 0.0
    errors: int = 0
    first_drawn: float | None = None
    last_drawn: float | None = None
    drift_checks: int = 0
    drifts: int = 0


def model_for(args: argparse.Namespace) -> str:
    return sam_image.MODEL if args.backend == "sam" else args.model


def build_request(args: argparse.Namespace, url: str) -> dict[str, Any]:
    if args.backend == "sam":
        return sam_image.sam_request(args.text, sam_image.image_part(url))
    return spark_vision.spark_request(
        model=args.model, prompt=spark_vision.locate_prompt(args.label_list), image_urls=[url],
        schema_name="LocateResult", schema=spark_vision.LocateResult.model_json_schema(),
        effort=args.effort, max_output_tokens=args.max_output_tokens,
    )


def shapes_from(args: argparse.Namespace, body: dict[str, Any], sent_size: tuple[int, int]) -> list[render.Shape]:
    """Response -> shapes in sent-frame pixels."""
    if args.backend == "sam":
        return [obj.shape(args.text) for obj in sam_image.parse_objects(body)]
    found = spark_vision.parse_result(output_text(body), "locate", None)
    return [render.Shape(o["label"], spark_vision.box_to_pixels(o["box_1000"], sent_size), o["confidence"])
            for o in found]


def estimate_per_call(args: argparse.Namespace, sent_size: tuple[int, int]) -> tuple[costs.Usage, costs.Usage]:
    """(typical, worst-case) usage of one request."""
    if args.backend == "sam":
        return costs.Usage(images=1), costs.Usage(images=1)
    schema = spark_vision.LocateResult.model_json_schema()
    text_chars = len(spark_vision.locate_prompt(args.label_list)) + len(json.dumps(schema))
    return costs.estimate_spark([sent_size], text_chars, args.max_output_tokens)


def downscale(frame: np.ndarray, max_side: int) -> np.ndarray:
    height, width = frame.shape[:2]
    factor = max_side / max(height, width)
    if factor >= 1:
        return frame
    return cv2.resize(frame, (round(width * factor), round(height * factor)), interpolation=cv2.INTER_AREA)


def iou(a: render.Box, b: render.Box) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def drift(tracked: list[render.Shape], fresh: list[render.Shape]) -> tuple[int, int]:
    """(checks, drifts): a tracked box drifted if no fresh API box of its label overlaps it at IoU >= 0.5."""
    checks = drifts = 0
    for shape in tracked:
        candidates = [f.box for f in fresh if f.label == shape.label]
        if candidates:
            checks += 1
            drifts += max(iou(shape.box, box) for box in candidates) < DRIFT_IOU
    return checks, drifts


def init_trackers(frame: np.ndarray, shapes: list[render.Shape]) -> list[Tracker]:
    height, width = frame.shape[:2]
    trackers = []
    for shape in shapes:
        x1, y1 = max(int(shape.box[0]), 0), max(int(shape.box[1]), 0)
        x2, y2 = min(int(shape.box[2]), width), min(int(shape.box[3]), height)
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        tracker = cv2.TrackerCSRT_create()
        tracker.init(frame, (x1, y1, x2 - x1, y2 - y1))
        trackers.append((tracker, shape))
    return trackers


def track_step(trackers: list[Tracker], frame: np.ndarray) -> list[render.Shape]:
    """Advance every tracker one frame; a lost tracker keeps its last box."""
    for i, (tracker, shape) in enumerate(trackers):
        ok, (x, y, w, h) = tracker.update(frame)
        if ok:
            trackers[i] = (tracker, replace(shape, box=(x, y, x + w, y + h)))
    return [shape for _, shape in trackers]


def _timed_post(client: Client, request: dict[str, Any]) -> tuple[ApiResult | None, float]:
    result = client.post_json("/responses", request)
    return result, time.perf_counter()


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(values, q)) if values else float("nan")


def print_session(stats: Stats, args: argparse.Namespace) -> None:
    done = len(stats.total_ms)
    print(f"\n=== live_probe session ({args.backend}{', dry run' if args.dry_run else ''}) ===")
    print(f"updates: {done}, errors: {stats.errors}")
    if not done:
        return
    for name, values in (("capture->draw", stats.total_ms), ("request->response", stats.roundtrip_ms)):
        print(f"{name + ' latency:':<27} p50 {percentile(values, 50):.0f} ms, p95 {percentile(values, 95):.0f} ms")
    span_s = stats.last_drawn - stats.first_drawn  # rate = draw-to-draw cadence, needs >= 2 updates
    rate = (done - 1) / span_s * 60 if span_s > 0 else float("nan")
    per_min = stats.cost_usd / done * rate
    print(f"effective update rate: {rate:.1f} updates/min ({done - 1} intervals over {span_s:.1f} s)")
    print(f"total cost: ${stats.cost_usd:.4f}; projected ${per_min:.4f}/min (${per_min * 60:.2f}/h) at this rate")
    if args.track:
        pct = 100 * stats.drifts / stats.drift_checks if stats.drift_checks else 0.0
        print(f"tracker drift vs next API result (IoU < {DRIFT_IOU}): {stats.drifts}/{stats.drift_checks} ({pct:.0f}%)")


class Probe:
    """Capture loop state: at most one request in flight, last result kept on screen."""

    def __init__(self, args: argparse.Namespace, client: Client):
        self.args = args
        self.client = client
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.pending: Pending | None = None
        self.shapes: list[render.Shape] = []
        self.trackers: list[Tracker] = []
        self.result_captured_at: float | None = None
        self.sent = 0
        self.last_send = -float("inf")
        self.stats = Stats()
        self.dry_dir = OUT / "live_probe"

    def wants_send(self, key: int, now: float) -> bool:
        if self.pending is not None or self.sent >= self.args.max_calls:
            return False
        if self.args.every is None:
            return key == SPACE
        return now - self.last_send >= self.args.every

    def send(self, frame: np.ndarray, t_capture: float) -> None:
        small = downscale(frame, SEND_MAX_SIDE)
        jpg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])[1].tobytes()
        request = build_request(self.args, data_url(jpg, "image/jpeg"))
        sent_size = (small.shape[1], small.shape[0])
        self.sent += 1
        self.last_send = t_capture
        print(f"\n[{self.sent}/{self.args.max_calls}] frame {sent_size[0]}x{sent_size[1]}, {len(jpg):,} bytes")
        if self.args.dry_run:
            self.dry_dir.mkdir(parents=True, exist_ok=True)
            path = self.dry_dir / f"dry_run_frame_{self.sent:02d}.jpg"
            cv2.imwrite(str(path), small)
            cv2.imshow("would send", small)
            self.client.post_json("/responses", request)
            typical, worst = estimate_per_call(self.args, sent_size)
            costs.print_estimate(model_for(self.args), typical, worst if self.args.backend == "spark" else None)
            print(f"  saved {path}")
            return
        tracked = [s for _, s in self.trackers]
        t_sent = time.perf_counter()
        future = self.executor.submit(_timed_post, self.client, request)
        self.pending = Pending(future, frame.copy(), t_capture, t_sent, sent_size, len(jpg), tracked)

    def collect(self) -> Completed | None:
        """If the in-flight request finished: log and price it, then swap in its shapes."""
        pending = self.pending
        if pending is None or not pending.future.done():
            return None
        self.pending = None
        try:  # keep the probe alive on API or parse errors; they are printed and counted
            result, t_response = pending.future.result()
            assert result is not None
            usage = costs.Usage.from_response(result.body)
            record = costs.record_call(
                script=SCRIPT, model=model_for(self.args), input_file=f"source:{self.args.source}",
                prompt_summary=self.args.text or self.args.labels, result=result, usage=usage, images_sent=1,
                notes=f"sent {pending.sent_size[0]}x{pending.sent_size[1]}, {pending.payload_bytes} bytes",
            )
            self.stats.cost_usd += record.cost_usd
            fresh = shapes_from(self.args, result.body, pending.sent_size)
        except Exception as error:
            self.stats.errors += 1
            print(f"  call failed: {error}")
            return None
        factor = pending.frame.shape[1] / pending.sent_size[0]
        self.shapes = [shape.scaled(factor) for shape in fresh]
        checks, drifts = drift(pending.tracked_at_capture, self.shapes)
        self.stats.drift_checks += checks
        self.stats.drifts += drifts
        self.result_captured_at = pending.t_capture
        if self.args.track:
            self.trackers = init_trackers(pending.frame, self.shapes)
        return Completed(pending, t_response, drifts)

    def caption(self, now: float) -> str:
        parts = [self.args.backend, f"calls {self.sent}/{self.args.max_calls}", f"${self.stats.cost_usd:.4f}"]
        if self.result_captured_at is not None:
            parts.append(f"age: {now - self.result_captured_at:.1f} s")
        if self.pending is not None:
            parts.append("in flight")
        if self.args.dry_run:
            parts.append("DRY RUN")
        return " | ".join(parts)

    def report(self, done: Completed, t_drawn: float) -> None:
        pending, t_response = done.pending, done.t_response
        total = (t_drawn - pending.t_capture) * 1000
        roundtrip = (t_response - pending.t_sent) * 1000
        self.stats.total_ms.append(total)
        self.stats.roundtrip_ms.append(roundtrip)
        self.stats.first_drawn = self.stats.first_drawn or t_drawn
        self.stats.last_drawn = t_drawn
        print(f"  capture->request {(pending.t_sent - pending.t_capture) * 1000:.0f} ms | request->response "
              f"{roundtrip:.0f} ms | response->draw {(t_drawn - t_response) * 1000:.0f} ms | total {total:.0f} ms | "
              f"{len(self.shapes)} shape(s)" + (f" | drifted {done.drifts}" if self.args.track else ""))

    def finish(self) -> None:
        """Wait for a request still in flight so it is paid for and logged."""
        if self.pending is not None:
            wait([self.pending.future])
            self.collect()
        self.executor.shutdown()


def open_source(source: str) -> tuple[cv2.VideoCapture, int]:
    capture = cv2.VideoCapture(int(source) if source.isdigit() else source)
    if not capture.isOpened():
        raise SystemExit(f"cannot open video source {source!r} (camera permission?)")
    fps = capture.get(cv2.CAP_PROP_FPS)
    file_delay_ms = round(1000 / fps) if not source.isdigit() and fps > 0 else 1  # play files in real time
    return capture, file_delay_ms


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m meta_eval.live_probe", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", choices=["sam", "spark"], required=True)
    parser.add_argument("--text", help="SAM concept prompt")
    parser.add_argument("--labels", help="comma-separated object names for Spark")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--on-key", action="store_true", help="SPACE sends the current frame (default)")
    mode.add_argument("--every", type=float, metavar="N", help=f"auto-send every N >= {MIN_INTERVAL_S:.0f} s")
    parser.add_argument("--max-calls", type=int, default=10, help="hard cap on requests this session")
    parser.add_argument("--track", action="store_true", help="CSRT-track the last boxes between updates")
    parser.add_argument("--source", default="0", help="camera index or video file")
    parser.add_argument("--model", default=spark_vision.DEFAULT_MODEL)
    parser.add_argument("--effort", default="minimal", choices=["minimal", "low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--max-output-tokens", type=int, default=4000)
    parser.add_argument("--dry-run", action="store_true", help="show/save the frame that would be sent; send nothing")
    args = parser.parse_args(argv)
    if args.every is not None and args.every < MIN_INTERVAL_S:
        parser.error(f"--every must be >= {MIN_INTERVAL_S:.0f} seconds")
    if args.backend == "sam" and not args.text:
        parser.error("--backend sam needs --text")
    if args.backend == "spark" and not args.labels:
        parser.error("--backend spark needs --labels")
    args.label_list = [label.strip() for label in (args.labels or "").split(",") if label.strip()]
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    capture, delay_ms = open_source(args.source)
    width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    factor = min(1.0, SEND_MAX_SIDE / max(width, height))
    sent_size = (round(width * factor), round(height * factor))
    model = model_for(args)
    typical, worst = estimate_per_call(args, sent_size)
    session_worst = costs.cost_usd(model, worst) * args.max_calls
    print(f"source {args.source}: {width}x{height}, frames sent at {sent_size[0]}x{sent_size[1]}; "
          f"mode {f'every {args.every:.1f} s' if args.every else 'SPACE'}; cap {args.max_calls} calls")
    costs.print_estimate(model, typical, worst if args.backend == "spark" else None)
    print(f"  worst case for the whole session: ${session_worst:.4f}")
    client = Client(dry_run=args.dry_run, max_calls=args.max_calls)
    if not args.dry_run:
        costs.check_budget(session_worst)

    probe = Probe(args, client)
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            now = time.perf_counter()
            if probe.trackers:
                probe.shapes = track_step(probe.trackers, frame)
            done = probe.collect()
            key = cv2.waitKey(delay_ms) & 0xFF
            if key in (ord("q"), ESC):
                break
            if probe.wants_send(key, now):
                probe.send(frame, now)
            cv2.imshow(WINDOW, render.draw(frame, probe.shapes, caption=probe.caption(time.perf_counter())))
            if done is not None:
                probe.report(done, time.perf_counter())
    finally:
        probe.finish()
        capture.release()
        cv2.destroyAllWindows()
        print_session(probe.stats, args)


if __name__ == "__main__":
    main()
