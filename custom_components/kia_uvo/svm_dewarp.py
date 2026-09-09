"""Fisheye dewarp for SVM camera views.

The 4 SVM camera segments are full-frame equidistant fisheye images. The
myHyundai app renders them through a 3D scene (3D car + ground + fisheye
textures), which we cannot reproduce exactly. This module is an approximate
2D fisheye->rectilinear remap used as a presentation aid; it is NOT a
faithful model of the car's surround view.

Model: equidistant fisheye  r_fish = f_fish * theta  (theta in radians).
For a fisheye whose full field of view FOV_fish fills the frame's shorter
side, the focal constant is  f_fish = (min(W,H)/2) / (FOV_fish/2 in radians).
The rectilinear output uses  r_rect = f_rect * tan(theta), with
f_rect = (out_W/2) / tan(FOV_out/2). We inverse-map each output pixel: from
its rectilinear radius R, theta = atan(R/f_rect); if theta is within the
fisheye's half-FOV, r_fish = f_fish*theta places the source pixel, otherwise
the output pixel is black (beyond the captured field).

Source pixels are sampled with bilinear interpolation (vectorized numpy) so
the upsampled edges of the rectilinear output stay smooth; the caller owns
the single JPEG re-encode (quality=100, 4:4:4) so there is no intermediate
lossy generation between the car's JPEG and the served image.

Per-camera FOV is auto-derived from the per-capture validAngleOfView
calibration already parsed into SVMDetails. The field layout (4 cams x 7
floats, leading value = camera order) is a best-effort guess: index
order*7+1 is treated as the horizontal FOV. Verify/tune against a daylight
capture before relying on it. This module imports numpy lazily so the
default SVM entity path (raw crops) stays dependency-free.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image


def camera_fov_deg(
    valid_angle_of_view: tuple[float, ...] | None, order: int
) -> float | None:
    """Best-effort horizontal FOV (degrees) for one SVM camera.

    validAngleOfView = 4 cams x 7 floats, [order, h_fov, v_fov, ...4 more].
    Returns None for TOP (order 4) or an absent/malformed field so the caller
    falls back to serving the raw fisheye.
    """
    if not valid_angle_of_view or not 0 <= order <= 3:
        return None
    # Require the full 4-camera layout; a shorter array means we would be
    # indexing into a field shape we do not understand.
    if len(valid_angle_of_view) < 28:
        return None
    base = order * 7
    fov = valid_angle_of_view[base + 1]
    if not 0 < fov <= 180:
        return None
    return float(fov)


def dewarp_fisheye(
    src: Image.Image,
    fisheye_fov_deg: float,
    output_fov_deg: float | None = None,
    out_size: tuple[int, int] | None = None,
) -> Image.Image | None:
    """Undistort one equidistant fisheye image to a rectilinear image.

    Args:
        src: source PIL image (a full-frame fisheye segment). Converted to
            RGB if needed; not modified.
        fisheye_fov_deg: full field of view the fisheye captures (degrees).
        output_fov_deg: rectilinear output FOV; defaults to the fisheye FOV
            (use the whole captured field). Smaller zooms in, less corner
            stretch.
        out_size: (width, height) of the output; defaults to the source size.

    Returns: a PIL RGB image, or None on import/parameter failure so the
    caller can fall back to the raw fisheye. The caller owns the JPEG encode
    so the pipeline keeps a single lossy generation (the car's JPEG).
    """
    try:
        import numpy as np
    except ImportError:
        return None
    try:
        if src.mode != "RGB":
            src = src.convert("RGB")
        arr = np.asarray(src)
        h, w = arr.shape[:2]
    except Exception:
        return None

    if not 0 < fisheye_fov_deg <= 180 or w == 0 or h == 0:
        return None
    out_w, out_h = out_size if out_size is not None else (w, h)
    out_fov = fisheye_fov_deg if output_fov_deg is None else output_fov_deg
    if not 0 < out_fov <= 180 or out_w == 0 or out_h == 0:
        return None

    fisheye_half = math.radians(fisheye_fov_deg) / 2.0
    out_half = math.radians(out_fov) / 2.0
    # r = f_fish * theta; r_edge = min side/2 at theta = fisheye_half.
    f_fish = (min(w, h) / 2.0) / fisheye_half
    # rectilinear: r = f_rect * tan(theta).
    f_rect = (out_w / 2.0) / math.tan(out_half)

    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    ox, oy = (out_w - 1) / 2.0, (out_h - 1) / 2.0

    ys, xs = np.indices((out_h, out_w), dtype=np.float32)
    dx = xs - ox
    dy = ys - oy
    r = np.sqrt(dx * dx + dy * dy)
    theta = np.arctan2(r, f_rect)  # rectilinear radius -> polar angle
    r_fish = f_fish * theta  # equidistant fisheye radius
    ang = np.arctan2(dy, dx)
    src_x = cx + r_fish * np.cos(ang)
    src_y = cy + r_fish * np.sin(ang)

    valid = theta <= fisheye_half
    # Bilinear sampling: blend the 4 source neighbors per output pixel so the
    # upsampled rectilinear edges stay smooth instead of nearest-neighbor
    # blockiness. Neighbors are clamped to the frame for samples near/beyond
    # the fisheye circle; out-of-circle pixels are zeroed by `valid` below.
    x0 = np.floor(src_x).astype(np.int32)
    y0 = np.floor(src_y).astype(np.int32)
    fx = (src_x - x0).astype(np.float32)[..., None]
    fy = (src_y - y0).astype(np.float32)[..., None]
    x0c = np.clip(x0, 0, w - 1)
    x1c = np.clip(x0 + 1, 0, w - 1)
    y0c = np.clip(y0, 0, h - 1)
    y1c = np.clip(y0 + 1, 0, h - 1)
    tl = arr[y0c, x0c].astype(np.float32)
    tr = arr[y0c, x1c].astype(np.float32)
    bl = arr[y1c, x0c].astype(np.float32)
    br = arr[y1c, x1c].astype(np.float32)
    top = tl * (1 - fx) + tr * fx
    bot = bl * (1 - fx) + br * fx
    out = top * (1 - fy) + bot * fy
    out = np.clip(out, 0, 255).astype(np.uint8)
    out[~valid] = 0

    from PIL import Image

    return Image.fromarray(out, "RGB")
