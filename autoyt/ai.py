"""Claude calls: YouTube metadata, copyright review, and scripts for prompt-only videos."""
import base64
import json
from pathlib import Path

import anthropic

from .config import CLAUDE_MODEL

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


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _ask(content: list, schema: dict, effort: str = "medium") -> dict:
    try:
        response = _get_client().beta.messages.create(
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
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise AIError("Claude returned no text.")
    return json.loads(text)


def _image_block(path: Path) -> dict:
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def analyze_video(frames: list[Path], duration: float, notes: str, has_audio: bool, keeps_original_audio: bool) -> dict:
    content: list = []
    for i, frame in enumerate(frames):
        content.append({"type": "text", "text": f"Frame {i} (at ~{duration * (i + 0.5) / len(frames):.0f}s):"})
        content.append(_image_block(frame))
    audio_note = (
        "The video has an audio track that will be kept, so consider whether it may contain commercial music."
        if has_audio and keeps_original_audio else
        "The original audio will be replaced or there is none."
    )
    content.append({"type": "text", "text": (
        f"These are {len(frames)} frames sampled from a {duration:.0f}-second video I am uploading to YouTube. "
        f"{audio_note}\n\nCreator's notes about the video: {notes.strip() or '(none given)'}\n\n"
        "Write the YouTube metadata, pick the frame index that makes the strongest thumbnail "
        "(sharp, expressive, uncluttered) as thumbnail_frame, and review copyright risk."
    )})
    result = _ask(content, VIDEO_SCHEMA)
    result["thumbnail_frame"] = max(0, min(int(result.get("thumbnail_frame", 0)), len(frames) - 1))
    return result


def write_video_script(prompt: str, target_seconds: int) -> dict:
    scenes = max(3, min(12, round(target_seconds / 12)))
    content = [{"type": "text", "text": (
        f"Create an original faceless explainer-style YouTube video from this idea:\n\n{prompt.strip()}\n\n"
        f"Write about {scenes} scenes for a video of roughly {target_seconds} seconds. Each scene has a short "
        "heading (max 6 words), on_screen_text (one or two short lines, max 18 words) and narration "
        "(spoken voice-over, 1-3 sentences, natural and conversational). The first scene is a hook, the last "
        "scene is a recap with a call to subscribe. background_colors: 2-3 hex colors for slide gradients that "
        "fit the topic. Also write the YouTube metadata and review copyright risk of your own script."
    )}]
    return _ask(content, SCRIPT_SCHEMA, effort="high")
