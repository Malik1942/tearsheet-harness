"""SAM 3.1 on one video with a concept prompt -> per-frame boxes/masks, overlay MP4, track summary.

    python -m meta_eval.sam_video fixtures/videos/x.mp4 --text "basketball" [--max-frames 300] [--dry-run]

The clip is re-encoded locally (first --max-frames frames, H.264, no audio, faststart) so billing is
capped before upload. Upload is synchronous (no polling); the file_id is cached per clip hash.
"""

from __future__ import annotations

import argparse
import itertools
import json
import shutil
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import cv2

from . import costs, render
from .client import OUT, Client, sha256
from .sam_image import MODEL, SamObject, parse_objects, sam_request

SCRIPT = "sam_video"
UPLOAD_TTL_S = 86_400  # Files API allows 3600..2592000; files never expire by default
UPLOAD_PLACEHOLDER = "<file_id returned by the upload>"


@dataclass(frozen=True)
class Clip:
    path: Path
    frames: int
    fps: float
    width: int
    height: int


def probe(path: Path) -> Clip:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
         "-show_entries", "stream=width,height,avg_frame_rate,nb_read_packets", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    ).stdout
    stream = json.loads(out)["streams"][0]
    return Clip(path, int(stream["nb_read_packets"]), float(Fraction(stream["avg_frame_rate"])),
                int(stream["width"]), int(stream["height"]))


def prepare_clip(src: Path, dst: Path, max_frames: int) -> Clip:
    """Re-encode the first `max_frames` frames as H.264 yuv420p (even size), no audio, faststart."""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-frames:v", str(max_frames), "-an",
         "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(dst)],
        check=True,
    )
    return probe(dst)


def cached_file_id(cache: Path, digest: str) -> str | None:
    if not cache.exists():
        return None
    entry = json.loads(cache.read_text())
    fresh = entry.get("expires_at", 0) > time.time() + 600
    return entry["file_id"] if entry.get("sha256") == digest and fresh else None


def upload(client: Client, clip: Clip, source: Path, cache: Path, digest: str) -> str:
    fields = {"purpose": "user_data", "expires_after[anchor]": "created_at",
              "expires_after[seconds]": str(UPLOAD_TTL_S)}
    result = client.post_file("/files", fields, clip.path)
    if result is None:
        return UPLOAD_PLACEHOLDER
    costs.record_call(script=SCRIPT, model="files", input_file=str(source), prompt_summary="upload",
                      result=result, usage=costs.Usage(), notes=f"{result.request_bytes} bytes")
    file_id = result.body["id"]
    expires_at = result.body.get("expires_at") or time.time() + UPLOAD_TTL_S
    cache.write_text(json.dumps({"sha256": digest, "file_id": file_id, "expires_at": expires_at}))
    return file_id


def track_summary(objects: list[SamObject], total_frames: int) -> dict[str, dict[str, Any]]:
    """Per object id: first/last frame, % of frames tracked, mean confidence, centre jumps."""
    by_id: dict[str, list[SamObject]] = defaultdict(list)
    for obj in sorted(objects, key=lambda o: o.frame):
        by_id[obj.object_id].append(obj)
    summary = {}
    for object_id, track in by_id.items():
        centres = [((o.box[0] + o.box[2]) / 2, (o.box[1] + o.box[3]) / 2) for o in track]
        jumps = [((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 for (x1, y1), (x2, y2) in itertools.pairwise(centres)]
        scores = [o.confidence for o in track if o.confidence is not None]
        first, last = track[0].frame, track[-1].frame
        summary[object_id] = {
            "first_frame": first,
            "last_frame": last,
            "frames_seen": len(track),
            "pct_frames_tracked": round(100 * len(track) / total_frames, 1),
            "pct_of_own_span": round(100 * len(track) / (last - first + 1), 1),
            "mean_confidence": round(sum(scores) / len(scores), 4) if scores else None,
            "mean_centre_jump_px": round(sum(jumps) / len(jumps), 2) if jumps else 0.0,
            "max_centre_jump_px": round(max(jumps), 2) if jumps else 0.0,
        }
    return summary


def write_overlay(clip: Clip, objects: list[SamObject], label: str, path: Path) -> None:
    by_frame: dict[int, list[render.Shape]] = defaultdict(list)
    for obj in objects:
        by_frame[obj.frame].append(obj.shape(label))
    capture = cv2.VideoCapture(str(clip.path))
    with render.VideoSink(path, clip.fps, (clip.width, clip.height)) as sink:
        index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            shapes = by_frame.get(index, [])
            sink.write(render.draw(frame, shapes, caption=f"frame {index}  objects {len(shapes)}"))
            index += 1
    capture.release()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m meta_eval.sam_video", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", type=Path)
    parser.add_argument("--text", required=True, help="one concept noun phrase")
    parser.add_argument("--max-frames", type=int, default=300, help="frames to keep and bill (default 300)")
    parser.add_argument("--dry-run", action="store_true", help="print requests and cost; send nothing")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise SystemExit("ffmpeg/ffprobe not found (brew install ffmpeg)")
    out_dir = OUT / args.video.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    clip = prepare_clip(args.video, out_dir / "sent.mp4", args.max_frames)
    digest = sha256(clip.path.read_bytes())
    cache = out_dir / "upload.json"
    file_id = cached_file_id(cache, digest)

    client = Client(dry_run=args.dry_run)
    client.reserve(1 + (file_id is None))
    planned = costs.Usage(frames=clip.frames)
    print(f"clip {clip.width}x{clip.height} @ {clip.fps:.2f} fps, {clip.frames} frames "
          f"({clip.frames / clip.fps:.1f} s, {clip.path.stat().st_size:,} bytes); "
          f"upload: {'cached ' + file_id if file_id else 'needed'}")
    costs.print_estimate(MODEL, planned, fps=clip.fps)
    if not args.dry_run:
        costs.check_budget(costs.cost_usd(MODEL, planned))

    start = time.perf_counter()
    file_id = file_id or upload(client, clip, args.video, cache, digest)
    request = sam_request(args.text, {"type": "input_video", "file_id": file_id}, mask_encoding="one_bit")
    result = client.post_json("/responses", request)
    if result is None:
        return
    wall_s = time.perf_counter() - start
    usage = costs.Usage.from_response(result.body)
    call = costs.record_call(script=SCRIPT, model=MODEL, input_file=str(args.video), prompt_summary=args.text,
                             result=result, usage=usage, frames_sent=clip.frames, fps=clip.fps)
    objects = parse_objects(result.body, media="video")

    frames: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for obj in objects:
        frames[obj.frame].append(obj.summary(with_rle=False))
    tracks = track_summary(objects, clip.frames)
    report = {
        "script": SCRIPT, "model": MODEL, "video": str(args.video), "prompt": args.text,
        "clip": {"frames": clip.frames, "fps": clip.fps, "width": clip.width, "height": clip.height},
        "frames_processed": usage.frames, "frames_with_objects": len(frames), "wall_time_s": round(wall_s, 2),
        "call": call.as_dict(), "frames": {str(k): v for k, v in sorted(frames.items())},
    }
    (out_dir / "sam_video.json").write_text(json.dumps(report, indent=2))
    (out_dir / "track_summary.json").write_text(json.dumps(tracks, indent=2))
    write_overlay(clip, objects, args.text, out_dir / "sam_video_overlay.mp4")
    print(f"  {len(tracks)} track(s), {len(frames)}/{clip.frames} frames with objects, wall {wall_s:.1f} s")
    for object_id, track in tracks.items():
        print(f"    id {object_id}: frames {track['first_frame']}-{track['last_frame']}, "
              f"{track['pct_frames_tracked']}% tracked, mean conf {track['mean_confidence']}")
    print(f"wrote {out_dir}/sam_video.json, track_summary.json, sam_video_overlay.mp4")


if __name__ == "__main__":
    main()
