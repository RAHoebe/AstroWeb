"""Deterministic CPU parallax. Depth is artistic, never a distance measurement."""
import math
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import numpy as np

cv2.setNumThreads(max(1, min(4, os.cpu_count() or 1)))


@dataclass
class Parameters:
    orientation: str = "portrait"
    method: str = "layered"
    motion: str = "orbit"
    zoom: float = 1.08
    focus_x: float = 0.5
    focus_y: float = 0.5
    pan_x: float = 0.018
    pan_y: float = 0.010
    depth: float = 0.65
    duration: float = 10
    fps: int = 24
    resolution: int = 1280
    star_source: str = "auto"
    blend: str = "auto"
    zoom_points: list = field(default_factory=list)

    @classmethod
    def parse(cls, raw=None):
        raw = {} if raw is None else raw
        if not isinstance(raw, dict) or set(raw) - set(cls.__dataclass_fields__):
            raise ValueError("invalid_parameters")
        values = asdict(cls())
        values.update(raw)
        for key, choices in {"orientation": {"portrait", "original"}, "method": {"layered", "depth", "kenburns"}, "motion": {"orbit", "drift", "push"}, "star_source": {"auto", "stars", "stars_laid"}, "blend": {"auto", "screen", "add"}}.items():
            if not isinstance(values[key], str) or values[key] not in choices:
                raise ValueError("invalid_parameters")
        for key, low, high in [("zoom", 1, 8), ("focus_x", 0, 1), ("focus_y", 0, 1), ("pan_x", -.08, .08), ("pan_y", -.08, .08), ("depth", 0, 1.5), ("duration", 4, 30)]:
            try:
                values[key] = float(values[key])
            except (ValueError, TypeError):
                raise ValueError("invalid_parameters") from None
            if not math.isfinite(values[key]) or not low <= values[key] <= high:
                raise ValueError("invalid_parameters")
        for key, choices in {"fps": {24, 30}, "resolution": {720, 1280, 1920, 2560, 3840}}.items():
            try:
                num = float(values[key])
                if not num.is_integer() or int(num) not in choices:
                    raise ValueError()
                values[key] = int(num)
            except (ValueError, TypeError, OverflowError):
                raise ValueError("invalid_parameters") from None
        points = values["zoom_points"]
        if not isinstance(points, list) or len(points) > 8:
            raise ValueError("invalid_parameters")
        for point in points:
            if not isinstance(point, dict) or set(point) - {"focus_x","focus_y","zoom","name"} or not {"focus_x","focus_y","zoom"} <= set(point):
                raise ValueError("invalid_parameters")
            if "name" in point and (not isinstance(point["name"],str) or len(point["name"]) > 100):
                raise ValueError("invalid_parameters")
            for key, low, high in (("focus_x",0,1),("focus_y",0,1),("zoom",1,8)):
                value = point[key]
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not low <= value <= high:
                    raise ValueError("invalid_parameters")
        if points:
            values.update({k:points[0][k] for k in ("zoom","focus_x","focus_y")})
        values["zoom_points"] = [dict(p) for p in points] if len(points)>1 or (points and points[0].get("name")) else []
        return cls(**values)


def read_rgb(path):
    # imdecode also supports Unicode paths on Windows and preserves 16-bit PNG/TIFF.
    data = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if data is None:
        raise ValueError("invalid_image")
    scale = 65535 if data.dtype == np.uint16 else 255
    if data.ndim == 2:
        data = cv2.cvtColor(data, cv2.COLOR_GRAY2RGB)
    elif data.shape[2] == 4:
        rgb = cv2.cvtColor(data[:, :, :3], cv2.COLOR_BGR2RGB).astype(np.float32) / scale
        return rgb * (data[:, :, 3:4].astype(np.float32) / scale)
    else:
        data = cv2.cvtColor(data, cv2.COLOR_BGR2RGB)
    return data.astype(np.float32) / scale


def resize_long(image, edge):
    h, w = image.shape[:2]
    factor = min(1, edge / max(w, h))
    size = (max(2, int(w * factor) // 2 * 2), max(2, int(h * factor) // 2 * 2))
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA)


def compose(background, stars, mode):
    if mode == "screen":
        return 1 - (1 - background) * (1 - stars)
    return np.clip(background + stars, 0, 1)


def select_layers(images, params):
    small = {k: resize_long(v, 640) for k, v in images.items()}
    sources = [params.star_source] if params.star_source != "auto" else ["stars_laid", "stars"]
    blends = [params.blend] if params.blend != "auto" else ["screen", "add"]
    scores = []
    for source in sources:
        for blend in blends:
            error = float(np.mean(np.abs(compose(small["starless"], small[source], blend) - small["final"])))
            scores.append({"source": source, "blend": blend, "mae": error})
    best = min(scores, key=lambda s: s["mae"])
    return best, scores


class Scene:
    def __init__(self, images, params):
        self.params = params
        self.choice, self.scores = select_layers(images, params)
        self.prepare(lambda key: images[key], params)

    @classmethod
    def from_paths(cls, paths, params):
        # Decode one original at a time. Keep only thumbnails for layer comparison.
        small = {key: resize_long(read_rgb(path), 640) for key, path in paths.items()}
        scene = cls.__new__(cls)
        scene.params = params
        scene.choice, scene.scores = select_layers(small, params)
        scene.prepare(lambda key: read_rgb(paths[key]), params)
        return scene

    def prepare(self, read, params):
        def oriented(key):
            image = read(key)
            if params.orientation == "portrait" and image.shape[1] > image.shape[0]:
                return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
            return image

        original = oriented("final")
        self.h, self.w = resize_long(original, params.resolution).shape[:2]
        self.margin = 1.025 + 2 * max(abs(params.pan_x), abs(params.pan_y)) * (1 + params.depth * 1.2)
        # Preserve source detail up to the closest camera position. OpenCV remap
        # accepts source sides shorter than 32767 pixels.
        peak = max((p["zoom"] for p in params.zoom_points), default=params.zoom)
        edge = min(32760, math.ceil(params.resolution * self.margin * (peak + .35 * params.depth)))

        def pixels(image):
            sampled = resize_long(image, edge)
            np.multiply(sampled, 65535, out=sampled)
            return np.rint(sampled, out=sampled).astype(np.uint16)

        final = pixels(original)
        del original
        self.xx, self.yy = np.meshgrid(np.arange(self.w, dtype=np.float32), np.arange(self.h, dtype=np.float32))
        if params.method == "kenburns":
            self.final = self.pyramid(final)
            return

        bg = pixels(oriented("starless"))
        stars = pixels(oriented(self.choice["source"]))
        lum = cv2.cvtColor(cv2.resize(bg, (self.w, self.h), interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(lum.astype(np.float32) / 65535, (0, 0), max(2, min(self.w, self.h) / 65))
        p10, p90 = np.percentile(blurred, [10, 90])
        self.depth = np.clip((blurred - p10) / max(float(p90 - p10), .01), 0, 1).astype(np.float32)

        brightness = stars.max(axis=2)
        count, labels = cv2.connectedComponents((brightness > .025 * 65535).astype(np.uint8))
        peaks = np.zeros(count, dtype=np.uint16)
        np.maximum.at(peaks, labels.ravel(), brightness.ravel())
        weights = np.clip((peaks.astype(np.float32) / 65535 - .14) / .50, 0, 1)
        weights[0] = 0
        del brightness
        screen = self.choice["blend"] == "screen"
        # Reuse the three input buffers for the corrected background and star
        # layers. Row blocks bound temporary float arrays on large originals.
        for row in range(0, bg.shape[0], 128):
            band = slice(row, row + 128)
            background = bg[band].astype(np.float32) / 65535
            light = stars[band].astype(np.float32) / 65535
            residual = final[band].astype(np.float32) / 65535 - compose(background, light, self.choice["blend"])
            background += residual / np.maximum(1 - light, .02) if screen else residual
            near = light * weights[labels[band], None]
            far = (light - near) / np.maximum(1 - near, .01) if screen else light - near
            bg[band] = np.rint(np.clip(background, 0, 1) * 65535)
            stars[band] = np.rint(np.clip(far, 0, 1) * 65535)
            final[band] = np.rint(near * 65535)
        del labels
        self.bg, self.far, self.near = (self.pyramid(layer) for layer in (bg, stars, final))

    def pyramid(self, image):
        levels = [image]
        while levels[-1].shape[0] >= 2 * self.h and levels[-1].shape[1] >= 2 * self.w:
            levels.append(cv2.pyrDown(levels[-1]))
        return levels

    def camera(self, phase):
        a = 2 * math.pi * phase
        if self.params.motion == "orbit":
            x, y, z = math.sin(a), math.cos(a), (1 - math.cos(a)) / 2
        elif self.params.motion == "drift":
            x, y, z = math.sin(a), math.sin(a), (1 - math.cos(a)) / 2
        else:
            x, y, z = math.sin(a) * .2, math.sin(a) * .2, (1 - math.cos(a)) / 2
        return x * self.params.pan_x * self.w, y * self.params.pan_y * self.h, z

    def camera_pose(self, phase, z):
        p = self.params
        if len(p.zoom_points)<=1:
            return ((p.focus_x-.5)*z, (p.focus_y-.5)*z, (p.zoom-1)*z, min(p.zoom-1,.35)*z)
        stops = [(0.,0.,0.,0.)]
        stops.extend((v["focus_x"]-.5,v["focus_y"]-.5,v["zoom"]-1,min(v["zoom"]-1,.35)) for v in p.zoom_points)
        stops.append(stops[0])
        position = (phase % 1)*(len(stops)-1)
        i = int(position)
        u = position-i
        u = u*u*(3-2*u)
        return tuple(a+(b-a)*u for a,b in zip(stops[i],stops[i+1]))

    def warp(self, image, dx, dy, pose, factor=1, relief=False):
        fx, fy, zoom, differential = pose
        # Keep the layers on the same target even at large magnifications.
        scale = self.margin * (1 + zoom + differential * (factor - 1))
        cx, cy = (self.w - 1) / 2, (self.h - 1) / 2
        center_x = cx + 2 * fx * cx - dx * factor / scale
        center_y = cy + 2 * fy * cy - dy * factor / scale
        mx = (self.xx - cx) / scale + np.clip(center_x, cx / scale, 2 * cx - cx / scale)
        my = (self.yy - cy) / scale + np.clip(center_y, cy / scale, 2 * cy - cy / scale)
        if relief:
            displacement = (self.depth - .5) * self.params.depth
            mx -= dx * displacement * .35 / scale
            my -= dy * displacement * .35 / scale
        level = image[0]
        for candidate in image[1:]:
            if candidate.shape[1] < self.w * scale:
                break
            level = candidate
        h, w = level.shape[:2]
        mx = ((mx + .5) * (w / self.w) - .5).astype(np.float32)
        my = ((my + .5) * (h / self.h) - .5).astype(np.float32)
        return cv2.remap(level, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE).astype(np.float32) / 65535

    def frame(self, phase):
        x, y, z = self.camera(phase)
        pose = self.camera_pose(phase,z)
        if self.params.method == "kenburns":
            return self.warp(self.final, x, y, pose)
        depth = self.params.depth
        bg = self.warp(self.bg, x, y, pose, 1 - .35 * depth, self.params.method == "depth")
        far = self.warp(self.far, x, y, pose, 1 + .3 * depth)
        near = self.warp(self.near, x, y, pose, 1 + 1.0 * depth)
        stars = compose(far, near, self.choice["blend"])
        return np.clip(compose(bg, stars, self.choice["blend"]), 0, 1)


def ffmpeg_executable():
    candidate = os.environ.get("ASTROWEB_FFMPEG") or shutil.which("ffmpeg")
    if not candidate or not Path(candidate).is_file():
        raise RuntimeError("ffmpeg_missing")
    return str(candidate)


def save_jpg(path, image, quality=91):
    data = np.rint(np.clip(image, 0, 1) * 255).astype(np.uint8)
    ok, encoded = cv2.imencode(".jpg", cv2.cvtColor(data, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("image_write_failed")
    encoded.tofile(path)


def render_video(paths, target, params, progress=lambda value: None):
    start = time.monotonic()
    scene = Scene.from_paths(paths, params)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.stem + ".part.mp4")
    stderr_file = target.with_suffix(".encode.log")
    command = [ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{scene.w}x{scene.h}", "-r", str(params.fps), "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-threads", "2", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(partial)]
    count = round(params.duration * params.fps)
    process = None
    try:
        with stderr_file.open("wb") as log:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for index in range(count):
                frame = np.rint(scene.frame(index / count) * 255).astype(np.uint8)
                process.stdin.write(frame.tobytes())
                if index % max(1, params.fps // 2) == 0:
                    progress(round(5 + index / count * 90, 1))
            process.stdin.close()
            if process.wait(timeout=180) != 0:
                raise RuntimeError("encode_failed")
        if partial.stat().st_size < 1000:
            raise RuntimeError("encode_failed")
        partial.replace(target)
        stderr_file.unlink(missing_ok=True)
    except BaseException:
        if process and process.poll() is None:
            process.kill()
            process.wait()
        partial.unlink(missing_ok=True)
        raise
    return {"width": scene.w, "height": scene.h, "frames": count, "seconds": round(time.monotonic() - start, 2), "choice": scene.choice, "candidates": scene.scores, "bytes": target.stat().st_size}

def gallery_preview_path(movie):
    return Path(movie).with_suffix(".preview.mp4")


def build_gallery_preview(movie):
    """Create an independently cacheable, silent gallery loop from the master."""
    target = gallery_preview_path(movie)
    if target.is_file():
        return
    partial = target.with_suffix(".part.mp4")
    scale = "scale=w='min(640,iw)':h='min(640,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2"
    try:
        subprocess.run([ffmpeg_executable(), "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(movie), "-an", "-vf", scale + ",fps=18", "-c:v", "libx264",
                        "-preset", "fast", "-crf", "25", "-threads", "2", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", str(partial)], check=True, capture_output=True, timeout=300,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
