# Media Extractors

Two small CLI tools:

- **`extract_transcripts.py`** — pulls plain-text transcripts from the
  long-form videos of a YouTube channel (default
  [`@projectorchannel`](https://www.youtube.com/@projectorchannel)).
- **`extract_instagram.py`** — downloads all feed posts (photos, videos,
  captions) from an Instagram profile via `instaloader`.

## Setup

```bash
pip install -r requirements.txt
```

## YouTube transcripts

```bash
# Default: all videos >= 10 min from @projectorchannel into ./transcripts/
python extract_transcripts.py

# Smoke test with just 2 videos
python extract_transcripts.py --limit 2

# Point at a different channel / threshold / output dir
python extract_transcripts.py \
  --channel https://www.youtube.com/@someotherchannel/videos \
  --min-duration 300 \
  --out ./out/
```

Flags:

| Flag             | Default                                                | Meaning                                      |
|------------------|--------------------------------------------------------|----------------------------------------------|
| `--channel`      | `https://www.youtube.com/@projectorchannel/videos`     | Channel videos page URL                      |
| `--min-duration` | `600` (seconds)                                        | Minimum video length to include              |
| `--out`          | `transcripts`                                          | Output directory                             |
| `--languages`    | `en,en-US,en-GB`                                       | Preferred transcript languages, in order     |
| `--limit`        | _(none)_                                               | Stop after N qualifying videos (for testing) |

## Output

Each transcript is written as
`transcripts/<upload_date>__<video_id>__<safe_title>.txt`. Failures are
appended to `transcripts/_errors.log`. Re-running the script skips videos
whose output already exists.

## Instagram posts

```bash
# First run: prompts for password (and 2FA code if enabled) and caches the
# session under ~/.config/instaloader/.
python extract_instagram.py --login YOUR_IG_USERNAME --target alexandra.danieli

# Later runs reuse the cached session and only pick up new posts:
python extract_instagram.py --login YOUR_IG_USERNAME --target alexandra.danieli
```

Flags:

| Flag       | Default             | Meaning                                       |
|------------|---------------------|-----------------------------------------------|
| `--login`  | _(required)_        | Instagram account to authenticate as          |
| `--target` | `alexandra.danieli` | Profile whose feed posts to download          |
| `--out`    | `instagram`         | Output directory (a `<target>/` subdir)       |
| `--sleep`  | `2.0`               | Seconds between posts (helps avoid rate caps) |

For each post you get, under `instagram/<target>/`:

- The media file(s): `.jpg` / `.mp4` (carousels produce multiple files).
- A `.txt` with the caption.

Re-running is incremental — posts already on disk are skipped.

**Caveats:**
- Instagram's ToS forbids scraping. Authenticating as the profile owner
  (or with the owner's permission) is the only compliant path.
- IG rate-limits aggressively. If you get 401/429, wait a few hours
  before retrying; raise `--sleep` if it happens repeatedly.
- Only feed posts are downloaded — no stories, highlights, or tagged.
