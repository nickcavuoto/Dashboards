#!/usr/bin/env python3
"""Download all feed posts (media + captions) from an Instagram profile.

Uses `instaloader`. Requires a logged-in session for the account you
authenticate as; feed posts of your own profile are fetched via the
normal profile iteration API.

First run:
    python extract_instagram.py --login YOUR_IG_USERNAME --target alexandra.danieli
You'll be prompted for your password (and 2FA code if enabled); the
session is cached under ~/.config/instaloader/ so later runs won't
prompt again.

Re-runs are incremental: already-downloaded posts are skipped.
"""
from __future__ import annotations

import argparse
import getpass
import sys
import time
from pathlib import Path

import instaloader
from instaloader.exceptions import (
    BadCredentialsException,
    ConnectionException,
    LoginRequiredException,
    ProfileNotExistsException,
    TwoFactorAuthRequiredException,
)

DEFAULT_TARGET = "alexandra.danieli"
DEFAULT_OUT = Path("instagram")


def build_loader(out_dir: Path, target: str) -> instaloader.Instaloader:
    """Configure instaloader to save only media + captions (no JSON sidecars)."""
    return instaloader.Instaloader(
        dirname_pattern=str(out_dir / "{target}"),
        filename_pattern="{date_utc:%Y-%m-%d_%H-%M-%S}_{shortcode}",
        download_pictures=True,
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,  # skip .json.xz sidecars
        compress_json=False,
        post_metadata_txt_pattern="{caption}",  # write caption to .txt
        storyitem_metadata_txt_pattern="",
        max_connection_attempts=3,
        request_timeout=30.0,
    )


def ensure_login(L: instaloader.Instaloader, username: str) -> None:
    """Load a cached session if present; otherwise prompt for password + 2FA."""
    try:
        L.load_session_from_file(username)
        print(f"Loaded cached session for {username}.", flush=True)
        return
    except FileNotFoundError:
        pass

    password = getpass.getpass(f"Password for Instagram user {username!r}: ")
    try:
        L.login(username, password)
    except TwoFactorAuthRequiredException:
        code = input("Two-factor code: ").strip()
        L.two_factor_login(code)
    L.save_session_to_file()
    print("Login successful; session cached for future runs.", flush=True)


def download_feed_posts(
    L: instaloader.Instaloader, target: str, sleep_between: float
) -> tuple[int, int, int]:
    """Iterate feed posts (oldest->newest order from IG) and download each.

    Returns (attempted, downloaded_or_skipped, failed).
    """
    try:
        profile = instaloader.Profile.from_username(L.context, target)
    except ProfileNotExistsException:
        print(f"ERROR: profile {target!r} does not exist.", file=sys.stderr)
        return 0, 0, 0

    attempted = ok = failed = 0
    for post in profile.get_posts():
        attempted += 1
        shortcode = post.shortcode
        try:
            # download_post returns True if anything was actually downloaded;
            # False means files already existed (fast_update behavior).
            L.download_post(post, target=target)
            ok += 1
            print(
                f"  [{attempted}] {shortcode}  "
                f"{post.date_utc.strftime('%Y-%m-%d')}  "
                f"{'video' if post.is_video else 'image'}"
                f"{f' (carousel x{post.mediacount})' if post.typename == 'GraphSidecar' else ''}",
                flush=True,
            )
        except (ConnectionException, LoginRequiredException) as e:
            failed += 1
            print(f"  [{attempted}] {shortcode}  ! {type(e).__name__}: {e}", flush=True)
            # Back off on connection / login errors; IG is rate limiting.
            time.sleep(30)
        except Exception as e:  # keep going on any per-post failure
            failed += 1
            print(f"  [{attempted}] {shortcode}  ! {type(e).__name__}: {e}", flush=True)

        if sleep_between:
            time.sleep(sleep_between)

    return attempted, ok, failed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default=DEFAULT_TARGET, help="Instagram username to download.")
    ap.add_argument("--login", required=True, help="Instagram username to authenticate as.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output directory.")
    ap.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        help="Seconds to wait between posts (helps avoid rate limits).",
    )
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    L = build_loader(args.out, args.target)

    try:
        ensure_login(L, args.login)
    except BadCredentialsException as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print(f"Downloading feed posts of @{args.target} into {args.out}/ ...", flush=True)
    attempted, ok, failed = download_feed_posts(L, args.target, args.sleep)
    print(
        f"\nDone. attempted={attempted} ok={ok} failed={failed}"
        f"  (output: {args.out}/{args.target}/)",
        flush=True,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
