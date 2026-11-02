"""Video editing with ffmpeg: format, loudness, fades, title card and ducked background music."""
import os
from pathlib import Path

from . import media

# YouTube re-encodes every upload, so a fast x264 preset at a low CRF loses nothing visible
# while being several times quicker than "medium" on laptop CPUs.
X264_PRESET = os.getenv("AUTOYT_X264_PRESET", "veryfast")
# 1080 by default; set AUTOYT_RESOLUTION=720 in .env to render ~2x faster on slow PCs.
_SHORT_SIDE = 720 if os.getenv("AUTOYT_RESOLUTION", "1080").strip() == "720" else 1080


def target_size(info: media.MediaInfo) -> tuple[int, int]:
    long_side = _SHORT_SIDE * 16 // 9
    return (_SHORT_SIDE, long_side) if info.vertical else (long_side, _SHORT_SIDE)


def finish_video(src: Path, out: Path, *, music: Path | None = None,
                 overlay: tuple[Path, int, int] | None = None,
                 replace_audio: bool = False, music_level: float = 0.18) -> Path:
    """Produce a YouTube-ready MP4 (H.264/AAC, 30 fps, faststart)."""
    info = media.probe(src)
    W, H = target_size(info)
    D = info.duration
    fade_out = max(0.0, D - 0.8)

    args: list = ["-i", src]
    idx = 1
    music_idx = overlay_idx = None
    if music:
        args += ["-stream_loop", "-1", "-i", music]
        music_idx, idx = idx, idx + 1
    if overlay:
        overlay_png, ox, oy = overlay
        args += ["-loop", "1", "-framerate", "30", "-t", f"{min(D, 6):.2f}", "-i", overlay_png]
        overlay_idx, idx = idx, idx + 1

    filters = [
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"setsar=1,fps=30,format=yuv420p,fade=t=in:st=0:d=0.5,fade=t=out:st={fade_out:.2f}:d=0.8[base]"
    ]
    vout = "[base]"
    if overlay_idx is not None:
        filters.append(
            f"[{overlay_idx}:v]format=rgba,fade=t=in:st=0.4:d=0.5:alpha=1,"
            f"fade=t=out:st={max(0.5, min(D, 6) - 1.2):.2f}:d=0.6:alpha=1[ov]"
        )
        filters.append(f"[base][ov]overlay={ox}:{oy}:eof_action=pass:format=yuv420[vid]")
        vout = "[vid]"

    keep_voice = info.has_audio and not replace_audio
    aout = None
    if keep_voice:
        filters.append("[0:a]aresample=44100,loudnorm=I=-14:TP=-1.5:LRA=11,aformat=channel_layouts=stereo[voice]")
        aout = "[voice]"
    if music_idx is not None:
        filters.append(f"[{music_idx}:a]atrim=0:{D:.2f},aformat=channel_layouts=stereo,volume={1.0 if not keep_voice else music_level}[mus]")
        if keep_voice:
            # Duck the music whenever the original audio (speech) is present.
            filters.append("[voice]asplit=2[v1][v2]")
            filters.append("[mus][v1]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=350[ducked]")
            filters.append("[v2][ducked]amix=inputs=2:duration=first:normalize=0[mixed]")
            aout = "[mixed]"
        else:
            filters.append("[mus]loudnorm=I=-16:TP=-1.5:LRA=11[mixed]")
            aout = "[mixed]"
    if aout is None:  # YouTube handles silent video fine, but some players dislike missing audio.
        filters.append(f"anullsrc=r=44100:cl=stereo,atrim=0:{D:.2f}[silence]")
        aout = "[silence]"
    filters.append(f"{aout}afade=t=in:st=0:d=0.4,afade=t=out:st={fade_out:.2f}:d=0.8[aud]")

    args += [
        "-filter_complex", ";".join(filters), "-map", vout, "-map", "[aud]",
        "-t", f"{D:.2f}", "-c:v", "libx264", "-preset", X264_PRESET, "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", out,
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    media.run(args)
    return out


def slides_to_video(scenes: list[tuple[Path, Path | None, float]], out: Path, work: Path) -> Path:
    """scenes: (slide image, narration wav or None, seconds). Builds one MP4 with narration."""
    work.mkdir(parents=True, exist_ok=True)
    segments = []
    for i, (img, voice, seconds) in enumerate(scenes):
        seg = work / f"seg_{i:02d}.mp4"
        frames = int(seconds * 30)
        # Slow push-in keeps static slides from feeling frozen.
        vf = (f"scale=2112:1188,zoompan=z='min(zoom+0.0004,1.06)':d={frames}:"
              f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30,"
              f"fade=t=in:st=0:d=0.35,fade=t=out:st={max(0.0, seconds - 0.35):.2f}:d=0.35,format=yuv420p")
        args = ["-loop", "1", "-framerate", "30", "-t", f"{seconds:.2f}", "-i", img]
        if voice:
            args += ["-i", voice, "-filter_complex",
                     f"[0:v]{vf}[v];[1:a]aresample=44100,aformat=channel_layouts=stereo,apad[a]",
                     "-map", "[v]", "-map", "[a]"]
        else:
            args += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-filter_complex",
                     f"[0:v]{vf}[v]", "-map", "[v]", "-map", "1:a"]
        args += ["-t", f"{seconds:.2f}", "-c:v", "libx264", "-preset", X264_PRESET, "-tune", "stillimage", "-crf", "18",
                 "-c:a", "aac", "-b:a", "192k", "-ar", "44100", seg]
        media.run(args)
        segments.append(seg)

    concat_list = work / "concat.txt"
    concat_list.write_text("".join(f"file '{s.as_posix()}'\n" for s in segments), encoding="utf-8")
    media.run(["-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", out])
    return out
