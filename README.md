# AutoYT-manager

Upload a video or type an idea. Using Gemini (free), ChatGPT or Claude, AutoYT-manager writes the title, description, hashtags and tags,
designs a thumbnail, composes copyright-free background music, edits the video, and uploads it to
your YouTube channel.

Everything runs on your own PC in a browser tab at `http://127.0.0.1:8000`.

## What it does

| Step | Video mode (you upload a clip) | Prompt mode (you type an idea) |
|---|---|---|
| Content | Your footage | The AI writes a scene-by-scene script. The app renders slides and an offline voice-over |
| Title, description, hashtags, tags | The AI looks at 8 frames from your video plus your notes | Written along with the script |
| Thumbnail | 1280×720, built from the frame the AI rates best, with bold text | Built from the first slide |
| Music | Generated from scratch by the app (calm, upbeat, lo-fi or epic) | Same |
| Editing | Scaled to 1080p (vertical videos stay vertical), loudness evened out, fades, title card, music that drops under speech | Slides with a slow zoom, voice-over and music |
| Upload | YouTube Data API: title, description, tags, category, visibility, thumbnail | Same |

### Choosing from suggestions (video mode)

When you upload a video, the AI studies it and gives you options to choose from. Every option is
pre-filled with the AI's top pick, marked **AI pick**:

- **Titles:** 4 options from different angles (curiosity, benefit, how-to, story). Each one is editable.
- **Thumbnails:** 3 finished designs, each using a different frame, text and colour. The text is editable.
- **Descriptions:** 3 styles (short, story, detailed/SEO). Each one is editable.
- **Hashtags:** 15 ranked suggestions. Tap to add or remove them. You also get tags and a category.
- **Music:** a 20-second preview of each style (calm, upbeat, lo-fi, epic), plus "No music", with the AI's reasoning.
- **Original sound:** keep your audio with music mixed underneath, or replace it with music only.
- **Settings:** title banner, visibility, made for kids and the synthetic-content disclosure.
- **Tips:** short ideas for improving the video, and the copyright check result.

Click **Create video & upload**. The app edits the video with your choices and uploads it to
YouTube Studio. If you tick **Let AI choose everything** when uploading, it skips this step and uses
the AI's top picks.

After a video is built, **Change choices** lets you pick again and rebuild it. You can also edit the
title, description, hashtags, tags, thumbnail text and visibility before uploading.

## Copyright protection

The app is built so that nothing it adds can trigger a copyright claim:

- **Music** is synthesised by the app's own code from sine and triangle waves and noise. No samples,
  loops or existing melodies are used, so Content ID has nothing to match. The description credits it
  as original music.
- **Thumbnails, title cards and slides** use only your own footage, generated gradients and the fonts
  installed on your PC.
- **Text**: the AI is told never to quote lyrics or scripts, and never to use other creators' or brands'
  names to attract views.
- **Copyright check**: before every upload, the AI reviews the frames and text for third-party material,
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

### 1. AI key (at least one)

You choose the AI model for each video in the app. Add one or more keys to `.env`, then restart the app:

| Provider | Default model | Cost | Get a key |
|---|---|---|---|
| **Gemini** | `gemini-3.8-flash` (the best free Gemini model) | **Free tier**, about 10 requests per minute | <https://aistudio.google.com/apikey> |
| **ChatGPT** | `gpt-6-astra` (OpenAI's flagship) | Paid. The OpenAI API has no free tier, and a ChatGPT subscription doesn't cover it | <https://platform.openai.com/api-keys> |
| **Claude** | `claude-opus-5-5` | Paid | <https://console.anthropic.com/settings/keys> |

```
GEMINI_API_KEY=...
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

To change models, set `GEMINI_MODEL` (for example `gemini-4-argon`, Google's paid top model), `OPENAI_MODEL`
(for example `gpt-6.1-sol` for a cheaper option) or `CLAUDE_MODEL`. Gemini's free tier may use your
prompts and frames to improve Google's products. Use a paid provider for footage you want kept private.

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
| Background music | Auto | The AI picks the mood. Choose "No music" for talks or music performances |
| Visibility | Private | Private, Unlisted or Public |
| Replace original audio | Off | The safest choice against music claims |
| Title card | On | Shows the title as a lower-third banner for the first ~5 seconds |
| Upload automatically | Off | Only fires when the copyright check passes with nothing flagged |
| Made for kids | Off | Required YouTube declaration |
| Altered or synthetic content | Off | YouTube's disclosure for realistic AI-generated or altered media |

Optional settings in `.env`:

- `AUTOYT_RESOLUTION=720` renders at 720p, about 2× faster on low-power laptops.
- `AUTOYT_X264_PRESET` sets the encoder speed. The default `veryfast` is fine, because YouTube re-encodes every upload anyway.
- `AI_PROVIDER` sets which AI is selected by default (`gemini`, `openai` or `claude`). `GEMINI_MODEL`, `OPENAI_MODEL` and `CLAUDE_MODEL` change the model.

## Project layout

```
app.py              FastAPI server and HTTP API
static/index.html   Web UI
autoyt/
  ai.py             Gemini / ChatGPT / Claude: metadata, copyright review, scripts (structured JSON output)
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
