"""Image I/O and drawing of masks, boxes and labels on BGR frames (OpenCV + Pillow)."""

from __future__ import annotations

import subprocess
import zlib
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

PALETTE = [(245, 135, 66), (66, 135, 245), (80, 200, 120), (200, 80, 200),
           (60, 200, 230), (90, 60, 230), (40, 150, 150), (230, 160, 40)]  # BGR
MASK_ALPHA = 0.45
FONT = cv2.FONT_HERSHEY_SIMPLEX

Box = tuple[float, float, float, float]  # left, top, right, bottom (half-open), frame pixels


@dataclass(frozen=True)
class Shape:
    """One detection to draw. `mask` is a bool raster spanning `box` (any resolution)."""

    label: str
    box: Box
    score: float | None = None
    mask: np.ndarray | None = None
    key: str = ""  # color key; defaults to the label

    def scaled(self, factor: float) -> Shape:
        left, top, right, bottom = self.box
        return replace(self, box=(left * factor, top * factor, right * factor, bottom * factor))


def color_for(key: str) -> tuple[int, int, int]:
    return PALETTE[zlib.crc32(key.encode()) % len(PALETTE)]


def load_image(path: Path) -> Image.Image:
    """Open an image upright (EXIF orientation applied) as RGB. Transparency is composited onto white."""
    image = ImageOps.exif_transpose(Image.open(path))
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        flat.info = dict(image.info)  # keep icc_profile etc. for encode()
        return flat
    return image.convert("RGB")


def fit(image: Image.Image, max_side: int) -> Image.Image:
    """Downscale so the long side is at most `max_side` (0 = unchanged)."""
    if not max_side or max(image.size) <= max_side:
        return image
    out = image.copy()
    out.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return out


def encode(image: Image.Image, as_png: bool = False) -> tuple[bytes, str]:
    """Encode for upload; returns (bytes, mime)."""
    buffer = BytesIO()
    if as_png:
        image.save(buffer, "PNG")
        return buffer.getvalue(), "image/png"
    # Pillow drops the ICC profile on JPEG save unless it is passed back in; the model may still ignore it.
    image.save(buffer, "JPEG", quality=95, icc_profile=image.info.get("icc_profile"))
    return buffer.getvalue(), "image/jpeg"


def to_bgr(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def draw(frame: np.ndarray, shapes: list[Shape], caption: str = "") -> np.ndarray:
    out = frame.copy()
    scale = max(0.5, max(out.shape[:2]) / 1600)
    for shape in shapes:
        color = color_for(shape.key or shape.label)
        x1, y1, x2, y2 = (int(round(v)) for v in shape.box)
        if shape.mask is not None:
            _blend_mask(out, shape.mask, (x1, y1, x2, y2), color)
        cv2.rectangle(out, (x1, y1), (x2 - 1, y2 - 1), color, max(2, round(2 * scale)))
        text = shape.label if shape.score is None else f"{shape.label} {shape.score:.2f}"
        _label(out, text, (x1, y1), color, scale)
    if caption:
        _label(out, caption, (4, 0), (40, 40, 40), scale)
    return out


def _blend_mask(out: np.ndarray, mask: np.ndarray, box: tuple[int, int, int, int], color: tuple[int, int, int]) -> None:
    x1, y1, x2, y2 = box
    if x2 <= x1 or y2 <= y1:
        return
    if mask.shape != (y2 - y1, x2 - x1):
        mask = cv2.resize(mask.astype(np.uint8), (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST).astype(bool)
    height, width = out.shape[:2]
    cx1, cy1, cx2, cy2 = max(x1, 0), max(y1, 0), min(x2, width), min(y2, height)
    if cx1 >= cx2 or cy1 >= cy2:
        return
    visible = mask[cy1 - y1:cy2 - y1, cx1 - x1:cx2 - x1]
    region = out[cy1:cy2, cx1:cx2]
    region[visible] = (region[visible] * (1 - MASK_ALPHA) + np.array(color) * MASK_ALPHA).astype(np.uint8)


def _label(out: np.ndarray, text: str, origin: tuple[int, int], color: tuple[int, int, int], scale: float) -> None:
    thickness = max(1, round(scale * 1.5))
    (tw, th), _ = cv2.getTextSize(text, FONT, scale, thickness)
    x, y = max(origin[0], 0), max(origin[1], th + 6)  # keep the label on-screen
    cv2.rectangle(out, (x, y - th - 6), (x + tw + 6, y), color, -1)
    cv2.putText(out, text, (x + 3, y - 4), FONT, scale, (255, 255, 255), thickness, cv2.LINE_AA)


class VideoSink:
    """Write BGR frames to an H.264 MP4 by piping raw frames into ffmpeg."""

    def __init__(self, path: Path, fps: float, size: tuple[int, int]):
        width, height = size
        self._proc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{width}x{height}",
             "-r", f"{fps:.3f}", "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
             str(path)],
            stdin=subprocess.PIPE,
        )

    def write(self, frame: np.ndarray) -> None:
        assert self._proc.stdin is not None
        self._proc.stdin.write(frame.tobytes())

    def __enter__(self) -> VideoSink:
        return self

    def __exit__(self, *exc: object) -> None:
        assert self._proc.stdin is not None
        self._proc.stdin.close()
        if self._proc.wait() != 0:
            raise RuntimeError("ffmpeg failed while writing the overlay video")
