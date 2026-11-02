"""YouTube Data API v3: OAuth sign-in, resumable upload, thumbnail, processing status."""
import random
import time
from pathlib import Path
from typing import Callable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from .config import CLIENT_SECRET_FILE, TOKEN_FILE

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
_RETRYABLE_STATUS = {500, 502, 503, 504}


class YouTubeError(RuntimeError):
    pass


def _save(creds: Credentials) -> None:
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")


def get_credentials(interactive: bool = False) -> Credentials | None:
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save(creds)
            return creds
        except Exception:
            creds = None
    if not interactive:
        return None
    if not CLIENT_SECRET_FILE.exists():
        raise YouTubeError(
            f"Missing {CLIENT_SECRET_FILE.name}. Create an OAuth 'Desktop app' client in Google Cloud Console "
            "(YouTube Data API v3 enabled) and save the JSON as client_secret.json in the project folder."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", open_browser=True)
    _save(creds)
    return creds


def disconnect() -> None:
    TOKEN_FILE.unlink(missing_ok=True)


def _service(creds: Credentials | None = None):
    creds = creds or get_credentials()
    if creds is None:
        raise YouTubeError("YouTube channel is not connected. Click 'Connect YouTube' first.")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def channel_info() -> dict | None:
    creds = get_credentials()
    if creds is None:
        return None
    items = _service(creds).channels().list(part="snippet", mine=True).execute().get("items", [])
    if not items:
        return {"title": "(no channel on this Google account)", "id": None}
    snip = items[0]["snippet"]
    return {"id": items[0]["id"], "title": snip["title"], "thumbnail": snip.get("thumbnails", {}).get("default", {}).get("url")}


def upload(video: Path, *, title: str, description: str, tags: list[str], category_id: str,
           privacy: str, made_for_kids: bool, synthetic_media: bool, thumbnail: Path | None,
           on_progress: Callable[[float], None] = lambda p: None) -> dict:
    yt = _service()
    body = {
        "snippet": {"title": title, "description": description, "tags": tags, "categoryId": category_id},
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": made_for_kids,
            "containsSyntheticMedia": synthetic_media,
        },
    }
    media_body = MediaFileUpload(str(video), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media_body)

    response, retries = None, 0
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                on_progress(status.progress())
            retries = 0
        except HttpError as e:
            if e.resp.status not in _RETRYABLE_STATUS or retries >= 6:
                raise YouTubeError(f"Upload failed: {_reason(e)}") from e
            retries += 1
            time.sleep(min(60, 2 ** retries + random.random()))
        except (ConnectionError, TimeoutError, OSError) as e:
            if retries >= 6:
                raise YouTubeError(f"Upload failed: network error ({e})") from e
            retries += 1
            time.sleep(min(60, 2 ** retries + random.random()))
    on_progress(1.0)

    result = {"video_id": response["id"], "url": f"https://youtu.be/{response['id']}", "warnings": []}
    if thumbnail and thumbnail.exists():
        try:
            yt.thumbnails().set(videoId=response["id"], media_body=MediaFileUpload(str(thumbnail), mimetype="image/jpeg")).execute()
        except HttpError as e:
            result["warnings"].append(
                "Custom thumbnail was not set (" + _reason(e) + "). Custom thumbnails need a phone-verified "
                "channel: youtube.com/verify. You can upload thumbnail.jpg manually in YouTube Studio."
            )
    return result


def processing_status(video_id: str) -> dict:
    items = _service().videos().list(part="status,processingDetails", id=video_id).execute().get("items", [])
    if not items:
        return {"uploadStatus": "unknown"}
    st = items[0].get("status", {})
    return {
        "uploadStatus": st.get("uploadStatus"),
        "rejectionReason": st.get("rejectionReason"),
        "failureReason": st.get("failureReason"),
        "privacyStatus": st.get("privacyStatus"),
        "processingStatus": items[0].get("processingDetails", {}).get("processingStatus"),
    }


def _reason(e: HttpError) -> str:
    try:
        import json
        err = json.loads(e.content.decode())["error"]
        return err.get("message") or str(e.resp.status)
    except Exception:
        return str(e)
