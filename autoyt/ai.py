"""AI calls (Claude, Gemini or ChatGPT): YouTube metadata, copyright review, and scripts for prompt videos.

All three providers get the same system prompt and the same JSON schema, and return the same dict.
"""
import base64
import json
import os
from pathlib import Path

from .config import CLAUDE_MODEL, GEMINI_MODEL, OPENAI_MODEL, provider_configured

MOODS = ["calm", "upbeat", "lofi", "epic", "none"]

# YouTube category IDs that are assignable in most regions.
CATEGORIES = {
    "1": "Film & Animation", "2": "Autos & Vehicles", "10": "Music", "15": "Pets & Animals",
    "17": "Sports", "19": "Travel & Events", "20": "Gaming", "22": "People & Blogs",
    "23": "Comedy", "24": "Entertainment", "25": "News & Politics", "26": "Howto & Style",
    "27": "Education", "28": "Science & Technology",
}

_COPYRIGHT_REVIEW = {
    "type": "object",
    "properties": {
        "risk": {"type": "string", "enum": ["low", "medium", "high"]},
        "issues": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["risk", "issues"],
    "additionalProperties": False,
}

_METADATA_PROPS = {
    "title": {"type": "string"},
    "description": {"type": "string"},
    "hashtags": {"type": "array", "items": {"type": "string"}},
    "tags": {"type": "array", "items": {"type": "string"}},
    "category_id": {"type": "string", "enum": list(CATEGORIES)},
    "thumbnail_text": {"type": "string"},
    "accent_color": {"type": "string"},
    "music_mood": {"type": "string", "enum": MOODS},
    "copyright_review": _COPYRIGHT_REVIEW,
}
_METADATA_REQUIRED = list(_METADATA_PROPS)

VIDEO_SCHEMA = {
    "type": "object",
    "properties": {**_METADATA_PROPS, "thumbnail_frame": {"type": "integer"}},
    "required": [*_METADATA_REQUIRED, "thumbnail_frame"],
    "additionalProperties": False,
}

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        **_METADATA_PROPS,
        "background_colors": {"type": "array", "items": {"type": "string"}},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "on_screen_text": {"type": "string"},
                    "narration": {"type": "string"},
                },
                "required": ["heading", "on_screen_text", "narration"],
                "additionalProperties": False,
            },
        },
    },
    "required": [*_METADATA_REQUIRED, "background_colors", "scenes"],
    "additionalProperties": False,
}

SYSTEM = """You are the producer behind a YouTube channel. You write metadata that is accurate to the video, \
specific, and clickable without being misleading.

Rules:
- title: at most 90 characters, no clickbait that the video does not deliver, no ALL CAPS sentences, no < or >.
- description: 2-4 short paragraphs. Open with a hook line that matches the title, then what the viewer \
gets, then a soft call to action. Do NOT put hashtags in the description; they are appended separately. No < or >.
- hashtags: 3-8 relevant hashtags, each starting with #, no spaces inside a hashtag.
- tags: 8-15 search keywords/phrases (no # symbol).
- thumbnail_text: 2-5 punchy words for the thumbnail; it must NOT simply repeat the title.
- accent_color: a hex color like #FFD400 that pops against the thumbnail image.
- music_mood: background music style that fits; choose "none" if music would hurt the video \
(for example a talk with no pauses or a music performance).
- Write in the language the user writes in, unless they ask for another one.

Copyright (be strict, this channel must not receive claims or strikes):
- Never quote song lyrics, film or book passages, or other people's scripts. All text must be original.
- Do not use other creators', brands', shows' or songs' names to attract views unless the video is genuinely \
about them (then describe, never imply endorsement or official status).
- copyright_review.risk = "high" if the material appears to contain third-party copyrighted content the \
uploader likely does not own: TV/film/broadcast footage, sports broadcasts, gameplay cut-scenes presented \
without commentary, music videos, concerts, other creators' videos, screenshots of paid content, or a \
recognisable commercial song in the audio. "medium" for visible logos/brands, posters or artwork that are \
prominent, or uncertainty you cannot resolve. "low" otherwise.
- List each concrete issue in copyright_review.issues (empty list when there are none)."""


class AIError(RuntimeError):
    pass


PROVIDERS = {
    "gemini": {"label": "Gemini", "model": GEMINI_MODEL, "key": "GEMINI_API_KEY", "free": True},
    "claude": {"label": "Claude", "model": CLAUDE_MODEL, "key": "ANTHROPIC_API_KEY", "free": False},
    "openai": {"label": "ChatGPT", "model": OPENAI_MODEL, "key": "OPENAI_API_KEY", "free": False},
}

# Provider-neutral message content: a list of ("text", str) and ("image", Path) parts.
Part = tuple[str, "str | Path"]
_clients: dict = {}


def _b64(path: Path) -> str:
    return base64.standard_b64encode(Path(path).read_bytes()).decode("ascii")


def _parse(text: str | None, label: str) -> dict:
    if not text:
        raise AIError(f"{label} returned an empty answer.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIError(f"{label} returned invalid JSON. Retry the job.") from e


# ---------------------------------------------------------------- Claude

def _ask_claude(parts: list[Part], schema: dict, effort: str) -> dict:
    import anthropic

    if "claude" not in _clients:
        _clients["claude"] = anthropic.Anthropic()
    content = [
        {"type": "text", "text": v} if kind == "text" else
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _b64(v)}}
        for kind, v in parts
    ]
    try:
        response = _clients["claude"].beta.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            system=SYSTEM,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.AuthenticationError as e:
        raise AIError("Claude API key is missing or invalid. Set ANTHROPIC_API_KEY in .env.") from e
    except anthropic.RateLimitError as e:
        raise AIError("Claude API rate limit reached. Wait a minute and retry the job.") from e
    except anthropic.BadRequestError as e:
        raise AIError(f"Claude rejected the request: {e.message}") from e
    except anthropic.APIStatusError as e:
        raise AIError(f"Claude API error ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise AIError("Could not reach the Claude API. Check your internet connection.") from e

    if response.stop_reason == "refusal":
        raise AIError("Claude declined to write metadata for this content.")
    if response.stop_reason == "max_tokens":
        raise AIError("Claude's answer was cut off. Try a shorter prompt.")
    return _parse(next((b.text for b in response.content if b.type == "text"), None), "Claude")


# ---------------------------------------------------------------- Gemini (free tier)

def _ask_gemini(parts: list[Part], schema: dict, effort: str) -> dict:
    from google import genai
    from google.genai import errors, types

    if "gemini" not in _clients:
        _clients["gemini"] = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    contents = [
        v if kind == "text" else types.Part.from_bytes(data=Path(v).read_bytes(), mime_type="image/jpeg")
        for kind, v in parts
    ]
    try:
        response = _clients["gemini"].models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                response_mime_type="application/json",
                response_json_schema=schema,
                max_output_tokens=16000,
            ),
        )
    except errors.ClientError as e:
        if e.code in (401, 403) or "API key" in str(e.message):
            raise AIError("Gemini API key is missing or invalid. Set GEMINI_API_KEY in .env "
                          "(get a free key at https://aistudio.google.com/apikey).") from e
        if e.code == 429:
            raise AIError("Gemini free-tier limit reached. Wait a minute (or until tomorrow) and retry.") from e
        raise AIError(f"Gemini rejected the request ({e.code}): {e.message}") from e
    except errors.APIError as e:
        raise AIError(f"Gemini API error ({e.code}): {e.message}") from e
    except OSError as e:
        raise AIError("Could not reach the Gemini API. Check your internet connection.") from e

    candidate = (response.candidates or [None])[0]
    reason = str(getattr(candidate, "finish_reason", "") or "")
    if candidate is None or any(r in reason for r in ("SAFETY", "PROHIBITED", "BLOCKLIST", "RECITATION")):
        raise AIError("Gemini declined to write metadata for this content.")
    if "MAX_TOKENS" in reason:
        raise AIError("Gemini's answer was cut off. Try a shorter prompt.")
    return _parse(response.text, "Gemini")


# ---------------------------------------------------------------- OpenAI (ChatGPT)

def _ask_openai(parts: list[Part], schema: dict, effort: str) -> dict:
    import openai

    if "openai" not in _clients:
        _clients["openai"] = openai.OpenAI()
    content = [
        {"type": "input_text", "text": v} if kind == "text" else
        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{_b64(v)}"}
        for kind, v in parts
    ]
    try:
        response = _clients["openai"].responses.create(
            model=OPENAI_MODEL,
            instructions=SYSTEM,
            input=[{"role": "user", "content": content}],
            text={"format": {"type": "json_schema", "name": "youtube_video", "schema": schema, "strict": True}},
            max_output_tokens=16000,
        )
    except openai.AuthenticationError as e:
        raise AIError("OpenAI API key is missing or invalid. Set OPENAI_API_KEY in .env.") from e
    except openai.RateLimitError as e:
        raise AIError("OpenAI rate limit or quota reached. The OpenAI API is pay-as-you-go: add credit at "
                      "https://platform.openai.com/settings/organization/billing.") from e
    except openai.BadRequestError as e:
        raise AIError(f"OpenAI rejected the request: {e.message}") from e
    except openai.APIStatusError as e:
        raise AIError(f"OpenAI API error ({e.status_code}): {e.message}") from e
    except openai.APIConnectionError as e:
        raise AIError("Could not reach the OpenAI API. Check your internet connection.") from e

    for item in response.output or []:
        for block in getattr(item, "content", None) or []:
            if getattr(block, "type", "") == "refusal":
                raise AIError("ChatGPT declined to write metadata for this content.")
    if response.status == "incomplete":
        raise AIError("ChatGPT's answer was cut off. Try a shorter prompt.")
    return _parse(response.output_text, "ChatGPT")


_ASK = {"claude": _ask_claude, "gemini": _ask_gemini, "openai": _ask_openai}


def available_providers() -> list[str]:
    return [p for p in PROVIDERS if provider_configured(p)]


def default_provider() -> str:
    preferred = os.getenv("AI_PROVIDER", "").strip().lower()
    if preferred in PROVIDERS and provider_configured(preferred):
        return preferred
    available = available_providers()
    return available[0] if available else "gemini"


def _ask(provider: str, parts: list[Part], schema: dict, effort: str = "medium") -> dict:
    if provider not in _ASK:
        raise AIError(f"Unknown AI provider '{provider}'.")
    if not provider_configured(provider):
        info = PROVIDERS[provider]
        raise AIError(f"{info['label']} is not set up. Add {info['key']} to the .env file and restart the app.")
    return _ASK[provider](parts, schema, effort)


def analyze_video(frames: list[Path], duration: float, notes: str, has_audio: bool, keeps_original_audio: bool,
                  provider: str = "gemini") -> dict:
    parts: list[Part] = []
    for i, frame in enumerate(frames):
        parts.append(("text", f"Frame {i} (at ~{duration * (i + 0.5) / len(frames):.0f}s):"))
        parts.append(("image", frame))
    audio_note = (
        "The video has an audio track that will be kept, so consider whether it may contain commercial music."
        if has_audio and keeps_original_audio else
        "The original audio will be replaced or there is none."
    )
    parts.append(("text", (
        f"These are {len(frames)} frames sampled from a {duration:.0f}-second video I am uploading to YouTube. "
        f"{audio_note}\n\nCreator's notes about the video: {notes.strip() or '(none given)'}\n\n"
        "Write the YouTube metadata, pick the frame index that makes the strongest thumbnail "
        "(sharp, expressive, uncluttered) as thumbnail_frame, and review copyright risk."
    )))
    result = _ask(provider, parts, VIDEO_SCHEMA)
    result["thumbnail_frame"] = max(0, min(int(result.get("thumbnail_frame", 0)), len(frames) - 1))
    return result


def write_video_script(prompt: str, target_seconds: int, provider: str = "gemini") -> dict:
    scenes = max(3, min(12, round(target_seconds / 12)))
    parts: list[Part] = [("text", (
        f"Create an original faceless explainer-style YouTube video from this idea:\n\n{prompt.strip()}\n\n"
        f"Write about {scenes} scenes for a video of roughly {target_seconds} seconds. Each scene has a short "
        "heading (max 6 words), on_screen_text (one or two short lines, max 18 words) and narration "
        "(spoken voice-over, 1-3 sentences, natural and conversational). The first scene is a hook, the last "
        "scene is a recap with a call to subscribe. background_colors: 2-3 hex colors for slide gradients that "
        "fit the topic. Also write the YouTube metadata and review copyright risk of your own script."
    ))]
    return _ask(provider, parts, SCRIPT_SCHEMA, effort="high")
