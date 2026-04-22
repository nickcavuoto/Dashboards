#!/usr/bin/env python3
"""Extract plain-text transcripts for long-form videos on a YouTube channel."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

DEFAULT_CHANNEL = "https://www.youtube.com/@projectorchannel/videos"
DEFAULT_MIN_DURATION = 600  # 10 minutes
DEFAULT_LANGUAGES = ("en", "en-US", "en-GB")
ERROR_LOG = "_errors.log"


@dataclass
class VideoMeta:
    id: str
    title: str
    duration: int
    upload_date: str  # YYYYMMDD or "" if unknown


def list_channel_videos(channel_url: str) -> list[VideoMeta]:
    """Enumerate channel videos with duration metadata via yt-dlp."""
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-json",
        "--ignore-errors",
        "--no-warnings",
    ]
    # In sandboxed environments whose egress proxy re-signs TLS with a
    # custom root, yt-dlp's bundled certifi CA list rejects the cert.
    # Honor an opt-in override.
    import os
    if os.environ.get("YTDLP_INSECURE") == "1":
        cmd.append("--no-check-certificates")
    cmd.append(channel_url)
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0 and not proc.stdout:
        raise RuntimeError(f"yt-dlp failed: {proc.stderr.strip()}")

    videos: list[VideoMeta] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid = entry.get("id")
        if not vid:
            continue
        duration = entry.get("duration")
        if duration is None:
            continue  # flat-playlist sometimes omits; skip so min-duration is enforceable
        videos.append(
            VideoMeta(
                id=vid,
                title=entry.get("title") or vid,
                duration=int(duration),
                upload_date=entry.get("upload_date") or "",
            )
        )
    return videos


def fetch_transcript(
    api: YouTubeTranscriptApi, video_id: str, languages: Iterable[str]
) -> list[dict] | None:
    """Return raw transcript segments, preferring manual then generated captions."""
    langs = list(languages)
    try:
        tlist = api.list(video_id)
    except (TranscriptsDisabled, VideoUnavailable, NoTranscriptFound):
        return None

    for finder in (tlist.find_manually_created_transcript, tlist.find_generated_transcript):
        try:
            return finder(langs).fetch().to_raw_data()
        except NoTranscriptFound:
            continue

    # Last resort: any language, try to translate to English if possible.
    for t in tlist:
        try:
            if t.is_translatable:
                return t.translate("en").fetch().to_raw_data()
            return t.fetch().to_raw_data()
        except Exception:
            continue
    return None


_WS_RE = re.compile(r"\s+")


def format_plain_text(segments: list[dict]) -> str:
    """Join segment text into readable paragraphs wrapped at ~80 chars."""
    joined = " ".join(seg.get("text", "").replace("\n", " ") for seg in segments)
    joined = _WS_RE.sub(" ", joined).strip()
    return "\n".join(textwrap.wrap(joined, width=80, break_long_words=False)) + "\n"


_FILENAME_BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def safe_filename(title: str, max_len: int = 80) -> str:
    cleaned = _FILENAME_BAD.sub(" ", title)
    cleaned = _WS_RE.sub(" ", cleaned).strip(" .")
    return cleaned[:max_len].rstrip(" .") or "untitled"


def output_path(out_dir: Path, v: VideoMeta) -> Path:
    date = v.upload_date or "00000000"
    return out_dir / f"{date}__{v.id}__{safe_filename(v.title)}.txt"


def log_error(out_dir: Path, video_id: str, title: str, msg: str) -> None:
    with (out_dir / ERROR_LOG).open("a", encoding="utf-8") as f:
        f.write(f"{video_id}\t{title}\t{msg}\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--channel", default=DEFAULT_CHANNEL)
    ap.add_argument("--min-duration", type=int, default=DEFAULT_MIN_DURATION)
    ap.add_argument("--out", type=Path, default=Path("transcripts"))
    ap.add_argument(
        "--languages",
        default=",".join(DEFAULT_LANGUAGES),
        help="Comma-separated preference list (e.g. en,en-US).",
    )
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    languages = [s.strip() for s in args.languages.split(",") if s.strip()]

    print(f"Listing videos on {args.channel} ...", flush=True)
    all_videos = list_channel_videos(args.channel)
    long_videos = [v for v in all_videos if v.duration >= args.min_duration]
    print(
        f"Found {len(all_videos)} videos; {len(long_videos)} "
        f">= {args.min_duration}s.",
        flush=True,
    )

    api = YouTubeTranscriptApi()
    processed = 0
    wrote = 0
    skipped = 0
    failed = 0

    for v in long_videos:
        if args.limit is not None and processed >= args.limit:
            break
        processed += 1

        dest = output_path(out_dir, v)
        if dest.exists():
            skipped += 1
            print(f"[skip {processed}] {v.id}  {v.title[:70]}", flush=True)
            continue

        mins, secs = divmod(v.duration, 60)
        print(
            f"[get  {processed}] {v.id}  ({mins:>3}:{secs:02d})  {v.title[:60]}",
            flush=True,
        )
        try:
            segments = fetch_transcript(api, v.id, languages)
        except Exception as e:  # network, parsing, etc.
            failed += 1
            log_error(out_dir, v.id, v.title, f"fetch error: {e!r}")
            print(f"      ! error: {e!r}", flush=True)
            time.sleep(1)
            continue

        if not segments:
            failed += 1
            log_error(out_dir, v.id, v.title, "no transcript available")
            print("      ! no transcript available", flush=True)
            continue

        dest.write_text(format_plain_text(segments), encoding="utf-8")
        wrote += 1

    print(
        f"\nDone. processed={processed} wrote={wrote} "
        f"skipped_existing={skipped} failed={failed}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
