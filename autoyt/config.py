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
# Best model on Gemini's free tier. Paid top model: gemini-4-argon.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
# OpenAI's flagship. Cheaper: gpt-6.1-sol, gpt-6-luna. (OpenAI's API has no free tier.)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-astra")

# Google OAuth "Desktop app" client downloaded from Google Cloud Console.
CLIENT_SECRET_FILE = Path(os.getenv("YOUTUBE_CLIENT_SECRET", ROOT / "client_secret.json"))
TOKEN_FILE = ROOT / "token.json"

# YouTube limits (https://developers.google.com/youtube/v3/docs/videos#properties)
MAX_TITLE = 100
MAX_DESCRIPTION = 5000
MAX_TAGS_CHARS = 500
MAX_HASHTAGS = 15


def provider_configured(provider: str) -> bool:
    keys = {
        "claude": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "openai": ("OPENAI_API_KEY",),
    }.get(provider, ())
    return any(os.getenv(k, "").strip() for k in keys)
