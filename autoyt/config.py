import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

WORKSPACE = ROOT / "workspace"
UPLOAD_DIR = WORKSPACE / "uploads"
JOBS_DIR = WORKSPACE / "jobs"
for _d in (UPLOAD_DIR, JOBS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")

# Google OAuth "Desktop app" client downloaded from Google Cloud Console.
CLIENT_SECRET_FILE = Path(os.getenv("YOUTUBE_CLIENT_SECRET", ROOT / "client_secret.json"))
TOKEN_FILE = ROOT / "token.json"

# YouTube limits (https://developers.google.com/youtube/v3/docs/videos#properties)
MAX_TITLE = 100
MAX_DESCRIPTION = 5000
MAX_TAGS_CHARS = 500
MAX_HASHTAGS = 15


def anthropic_configured() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))
