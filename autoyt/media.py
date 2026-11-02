"""Thin wrappers around the ffmpeg binary bundled by imageio-ffmpeg (no system install needed)."""
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
# Hide the console window ffmpeg would otherwise flash on Windows.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class FFmpegError(RuntimeError):
    pass


def run(args: list[str]) -> str:
    proc = subprocess.run(
        [FFMPEG, "-hide_banner", "-nostdin", "-y", *map(str, args)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=_NO_WINDOW,
    )
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise FFmpegError(f"ffmpeg failed:\n{tail}")
    return proc.stderr


@dataclass
class MediaInfo:
    duration: float
    width: int
    height: int
    has_audio: bool

    @property
    def vertical(self) -> bool:
        return self.height > self.width


def probe(path: Path) -> MediaInfo:
    # `ffmpeg -i` with no output exits non-zero but prints stream info to stderr.
    proc = subprocess.run(
        [FFMPEG, "-hide_banner", "-nostdin", "-i", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=_NO_WINDOW,
    )
    info = proc.stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", info)
    if not m:
        raise FFmpegError(f"Could not read media file {path.name}")
    duration = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])

    width = height = 0
    v = re.search(r"Stream #[^\n]*Video:[^\n]*?(\d{2,5})x(\d{2,5})", info)
    if v:
        width, height = int(v[1]), int(v[2])
        # Phone footage stores portrait video as landscape + a rotation flag;
        # ffmpeg auto-rotates when decoding, so report the displayed size.
        rot = re.search(r"rotation of (-?\d+(?:\.\d+)?) degrees|rotate\s*:\s*(-?\d+)", info)
        if rot and abs(round(float(rot[1] or rot[2]))) % 180 == 90:
            width, height = height, width

    return MediaInfo(duration, width, height, has_audio=bool(re.search(r"Stream #[^\n]*Audio:", info)))


def extract_frames(path: Path, count: int, out_dir: Path, duration: float) -> list[Path]:
    """Grab `count` evenly spaced frames (skipping the very start/end, which are often black)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(count):
        t = duration * (i + 0.5) / count
        out = out_dir / f"frame_{i:02d}.jpg"
        run(["-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", "-vf", "scale=1280:-2", "-q:v", "3", out])
        if out.exists():
            frames.append(out)
    return frames


def audio_duration(path: Path) -> float:
    return probe(path).duration
