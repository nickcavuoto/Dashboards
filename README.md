# YouTube Transcript Extractor

Pulls plain-text transcripts from the long-form videos of a YouTube channel.
Defaults are tuned for
[`@projectorchannel`](https://www.youtube.com/@projectorchannel).

## Setup

```bash
pip install -r requirements.txt
```

## Usage

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
