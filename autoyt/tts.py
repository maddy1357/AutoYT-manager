"""Offline text-to-speech using the operating system's voices (Windows SAPI via pyttsx3).

Runs in a child process: pyttsx3's COM engine is not safe to reuse across worker threads.
"""
import subprocess
import sys
from pathlib import Path

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def synthesize(text: str, out_wav: Path, rate: int = 175, timeout: int = 120) -> Path | None:
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    text_file = out_wav.with_suffix(".txt")
    text_file.write_text(text, encoding="utf-8")
    try:
        subprocess.run(
            [sys.executable, "-m", "autoyt.tts", str(text_file), str(out_wav), str(rate)],
            cwd=Path(__file__).resolve().parent.parent, check=True, timeout=timeout,
            capture_output=True, creationflags=_NO_WINDOW,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    return out_wav if out_wav.exists() and out_wav.stat().st_size > 1000 else None


def _main(text_file: str, out_wav: str, rate: str) -> None:
    import pyttsx3

    engine = pyttsx3.init()
    engine.setProperty("rate", int(rate))
    engine.save_to_file(Path(text_file).read_text(encoding="utf-8"), out_wav)
    engine.runAndWait()


if __name__ == "__main__":
    _main(*sys.argv[1:4])
