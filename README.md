# AutoYT-manager

Upload a video or type an idea. AutoYT-manager writes the title, description, hashtags and tags,
designs a thumbnail, composes copyright-free background music, edits the video, and uploads it to
your YouTube channel.

Everything runs on your own PC in a browser tab at `http://127.0.0.1:8000`.

## What it does

| Step | Video mode (you upload a clip) | Prompt mode (you type an idea) |
|---|---|---|
| Content | Your footage | Claude writes a scene-by-scene script. The app renders slides and an offline voice-over |
| Title, description, hashtags, tags | Claude looks at 8 frames from your video plus your notes | Written along with the script |
| Thumbnail | 1280×720, built from the frame Claude rates best, with bold text | Built from the first slide |
| Music | Generated from scratch by the app (calm, upbeat, lo-fi or epic) | Same |
| Editing | Scaled to 1080p (vertical videos stay vertical), loudness evened out, fades, title card, music that drops under speech | Slides with a slow zoom, voice-over and music |
| Upload | YouTube Data API: title, description, tags, category, visibility, thumbnail | Same |

You can edit the title, description, hashtags, tags, thumbnail text and visibility before uploading.

## Copyright protection

The app is built so that nothing it adds can trigger a copyright claim:

- **Music** is synthesised by the app's own code from sine and triangle waves and noise. No samples,
  loops or existing melodies are used, so Content ID has nothing to match. The description credits it
  as original music.
- **Thumbnails, title cards and slides** use only your own footage, generated gradients and the fonts
  installed on your PC.
- **Text**: Claude is told never to quote lyrics or scripts, and never to use other creators' or brands'
  names to attract views.
- **Copyright check**: before every upload, Claude reviews the frames and text for third-party material,
  such as TV or movie footage, sports broadcasts, music videos, other creators' clips and prominent logos.
  It also checks whether you kept the clip's original audio.
- **Upload gate**: if anything is flagged, the video is held as **Needs review**. It won't upload, even with
  auto-upload on, until you tick "I own or have licensed everything in this video".
- **Replace original audio**: a checkbox that removes the clip's own sound and keeps only the generated
  music. Use it if any song, radio or TV was playing in the background. That is the most common cause of claims.

The app can't see inside YouTube's own Content ID system, so no tool can guarantee zero claims. Videos
upload as **Private** by default. Open YouTube Studio → Content → your video and check that "Copyright"
under **Checks** is clear. Only then switch the video to Public.

## Setup (Windows)

You need Python 3.11 or newer. ffmpeg is downloaded automatically through pip.

```bat
git clone https://github.com/maddy1357/AutoYT-manager.git
cd AutoYT-manager
run.bat
```

`run.bat` creates a virtual environment, installs the packages, creates `.env`, and opens the app.

### 1. Claude API key

Create a key at <https://console.anthropic.com/settings/keys> and put it in `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Connect your YouTube channel (one-time)

1. Open <https://console.cloud.google.com/>, create a project, then go to **APIs & Services → Library**
   and enable **YouTube Data API v3**.
2. Under **APIs & Services → OAuth consent screen**, choose **External**, fill in the app name and
   your email, and add your Google account under **Test users**.
3. Under **APIs & Services → Credentials**, choose **Create credentials → OAuth client ID** with
   application type **Desktop app**. Download the JSON file.
4. Save that file in the project folder as `client_secret.json`.
5. In the app, click **Connect YouTube** and sign in with the Google account that owns the channel.

Things Google enforces, not this app:

- **Uploads are private until Google audits your project.** Videos uploaded through a new, unverified
  API project are locked to Private. To publish videos as Public through the API, request an audit at
  <https://support.google.com/youtube/contact/yt_api_form>. Until then, upload as Private and switch to
  Public in YouTube Studio.
- **Custom thumbnails** need a phone-verified channel (<https://www.youtube.com/verify>). If yours isn't
  verified, the video still uploads and the app tells you to add `thumbnail.jpg` yourself.
- **Sign-in lasts 7 days while your consent screen is in "Testing"**. Click **Connect YouTube** again when
  it expires, or publish the consent screen.
- **The default API quota** is 10,000 units per day. One upload costs about 1,600 units, so roughly
  6 uploads per day.

## Options

| Option | Default | Notes |
|---|---|---|
| Background music | Auto | Claude picks the mood. Choose "No music" for talks or music performances |
| Visibility | Private | Private, Unlisted or Public |
| Replace original audio | Off | The safest choice against music claims |
| Title card | On | Shows the title as a lower-third banner for the first ~5 seconds |
| Upload automatically | Off | Only fires when the copyright check passes with nothing flagged |
| Made for kids | Off | Required YouTube declaration |
| Altered or synthetic content | Off | YouTube's disclosure for realistic AI-generated or altered media |

Optional settings in `.env`:

- `AUTOYT_RESOLUTION=720` renders at 720p, about 2× faster on low-power laptops.
- `AUTOYT_X264_PRESET` sets the encoder speed. The default `veryfast` is fine, because YouTube re-encodes every upload anyway.
- `CLAUDE_MODEL` sets the Claude model. The default is `claude-opus-5-5`.

## Project layout

```
app.py              FastAPI server and HTTP API
static/index.html   Web UI
autoyt/
  ai.py             Claude: metadata, copyright review, scripts (structured JSON output)
  pipeline.py       Job runner: video mode and prompt mode, copyright policy, upload
  editor.py         ffmpeg editing: scaling, loudness, fades, title card, ducked music, slideshow
  music.py          Procedural royalty-free music synthesiser
  graphics.py       Thumbnail, title card and slide rendering (Pillow)
  tts.py            Offline voice-over (Windows speech engine via pyttsx3)
  youtube.py        OAuth sign-in, resumable upload, thumbnail, processing status
  media.py          ffmpeg helpers (bundled ffmpeg from imageio-ffmpeg)
```

Job files (final video, thumbnail, music, frames) are saved in `workspace/jobs/<job-id>/`.
`.env`, `client_secret.json` and `token.json` are git-ignored. Never commit them.

## License

MIT
