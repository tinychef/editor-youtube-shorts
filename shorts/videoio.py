"""Streaming frame IO through ffmpeg pipes (raw RGB/gray), so long videos never sit in memory."""
import subprocess

import numpy as np

from .util import need


class Reader:
    def __init__(self, path, size=None, fmt="rgb24", fps=None, start=0.0):
        need("ffmpeg")
        self.w, self.h = size
        self.ch = 1 if fmt == "gray" else 3
        vf = [f"scale={self.w}:{self.h}:flags=area"]
        if fps:
            vf.insert(0, f"fps={fps:g}")
        seek = ["-ss", f"{start:.6f}"] if start > 0 else []
        cmd = ["ffmpeg", "-v", "error", *seek, "-i", str(path), "-vf", ",".join(vf), "-f", "rawvideo", "-pix_fmt", fmt, "-"]
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10 ** 7)
        self.n = self.w * self.h * self.ch

    def read(self):
        b = self.p.stdout.read(self.n)
        if len(b) < self.n:
            return None
        a = np.frombuffer(b, np.uint8)
        return a.reshape(self.h, self.w) if self.ch == 1 else a.reshape(self.h, self.w, 3)

    def __iter__(self):
        while True:
            f = self.read()
            if f is None:
                break
            yield f

    def close(self):
        try:
            self.p.stdout.close()
            self.p.kill()
            self.p.wait(timeout=5)
        except Exception:
            pass


class Writer:
    def __init__(self, path, size, fps, fmt="rgb24", codec="h264", crf=17, preset="medium", extra=()):
        w, h = size
        enc = {
            "h264": ["-vf", "scale=out_color_matrix=bt709:out_range=tv", "-c:v", "libx264", "-preset", preset,
                     "-crf", str(crf), "-pix_fmt", "yuv420p", "-profile:v", "high", "-colorspace", "bt709",
                     "-color_primaries", "bt709", "-color_trc", "bt709", "-movflags", "+faststart"],
            "ffv1": ["-c:v", "ffv1", "-level", "3"],
        }[codec]
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", fmt, "-s", f"{w}x{h}", "-r", f"{fps:g}",
               "-i", "-", *enc, *extra, str(path)]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10 ** 7)

    def write(self, frame):
        self.p.stdin.write(np.ascontiguousarray(frame).tobytes())

    def close(self):
        self.p.stdin.close()
        err = self.p.stderr.read().decode("utf8", "replace")
        if self.p.wait() != 0:
            raise RuntimeError("ffmpeg (escritura) falló:\n" + err[-2000:])
