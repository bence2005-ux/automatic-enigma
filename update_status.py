"""
Daily Server Status Updater
----------------------------
For each region (NA / EU / ASIA):
  - The colored ANSI box shows the LIVE current local clock time. This is
    only as fresh as the last run, so the workflow must run frequently
    (e.g. every 15 minutes — see the cron schedule in the workflow file)
    for it to feel live rather than stale.
  - The bullet lines use real Discord timestamps (<t:UNIX:R>), which Discord
    renders live client-side and auto-counts down with zero drift — these
    stay accurate even between runs.

Run this on a short interval via GitHub Actions (see daily-update.yml).

Required environment variables (set as GitHub Actions secrets):
  WEBHOOK_URL   - your Discord webhook URL
  MESSAGE_ID    - the ID of the message to edit/delete (leave blank on first run)

Optional:
  MODE          - "edit" (default) or "delete_resend"
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone

import requests

# ----------------------------------------------------------------------
# CONFIG — Honkai: Star Rail server reset schedule
# ----------------------------------------------------------------------
# HoYoverse server offsets are FIXED year-round — they do NOT shift for
# daylight saving, unlike city timezones (e.g. America/New_York). That's why
# these use plain UTC offsets instead of ZoneInfo city names:
#   NA    -> UTC-5  (fixed EST, never becomes EDT)
#   EU    -> UTC+1  (fixed CET, never becomes CEST)
#   ASIA  -> UTC+8  (China Standard Time — NOT Tokyo, which is UTC+9)

REGIONS = {
    "NA": {
        "utc_offset_hours": -5,
        "ansi_color": "31",   # red
    },
    "EU": {
        "utc_offset_hours": 1,
        "ansi_color": "37",   # white/gray
    },
    "ASIA": {
        "utc_offset_hours": 8,
        "ansi_color": "33",   # yellow
    },
}

# HSR's daily reset happens at 04:00 server time (confirmed across all three
# regions) — NOT midnight.
DAILY_RESET_HOUR = 4

# Weekly reset (Nameless Honor, Simulated Universe, etc.) is also 04:00,
# every Monday, server time.
WEEKLY_RESET_WEEKDAY = 0  # Monday
WEEKLY_RESET_HOUR = 4

MEMBER_COUNT = "1,781,913"

# ----------------------------------------------------------------------
# EMBED IMAGE
# ----------------------------------------------------------------------
# Points at a file living in your GitHub repo. Upload/replace this file
# whenever you want to change the image — keep the same filename and the
# embed will automatically pick up the new version on the next run.
#
# Uses raw.githubusercontent.com (GitHub's raw file CDN), which is more
# reliable for hotlinking than the normal github.com blob URL.
GITHUB_USER = "bence2005-ux"
GITHUB_REPO = "daily-bot"
GITHUB_BRANCH = "main"
IMAGE_FILENAME = "status_image.png"  # <-- change this if you name the file differently

IMAGE_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/"
    f"{GITHUB_BRANCH}/{IMAGE_FILENAME}"
)

# Cache-busting: Discord (and GitHub's own CDN) cache images by URL, so if
# you just overwrite the file with the same name, viewers can keep seeing
# the old cached version for a while. Appending the current commit SHA as a
# query param changes the URL every time you push a new image, forcing a
# fresh fetch. GITHUB_SHA is set automatically by GitHub Actions; falls back
# to a timestamp when running locally outside Actions.
_cache_buster = os.environ.get("GITHUB_SHA", str(int(datetime.now().timestamp())))[:8]
IMAGE_URL = f"{IMAGE_URL}?v={_cache_buster}"

WEBHOOK_URL = os.environ["WEBHOOK_URL"]
MESSAGE_ID = os.environ.get("MESSAGE_ID", "").strip()
MODE = os.environ.get("MODE", "edit").strip().lower()  # "edit" or "delete_resend"


# ----------------------------------------------------------------------
# TIME HELPERS
# ----------------------------------------------------------------------

def next_daily_reset(now_local: datetime) -> datetime:
    reset = now_local.replace(hour=DAILY_RESET_HOUR, minute=0, second=0, microsecond=0)
    if reset <= now_local:
        reset += timedelta(days=1)
    return reset


def next_weekly_reset(now_local: datetime) -> datetime:
    days_ahead = (WEEKLY_RESET_WEEKDAY - now_local.weekday()) % 7
    reset = now_local.replace(hour=WEEKLY_RESET_HOUR, minute=0, second=0, microsecond=0)
    reset += timedelta(days=days_ahead)
    if reset <= now_local:
        reset += timedelta(days=7)
    return reset


# ----------------------------------------------------------------------
# BUILD EMBED
# ----------------------------------------------------------------------

def build_field(region_name: str, cfg: dict) -> dict:
    tz = timezone(timedelta(hours=cfg["utc_offset_hours"]))
    now_local = datetime.now(tz)

    daily_reset_dt = next_daily_reset(now_local)
    weekly_reset_dt = next_weekly_reset(now_local)

    # Live current local clock time — this is only as fresh as the last run,
    # so the workflow needs to run frequently (e.g. every 15 min) for this
    # to look "live" rather than stale.
    current_time_str = now_local.strftime("%I:%M %p").lstrip("0")

    # Unix timestamps for Discord's native <t:...:R> relative format —
    # Discord renders these client-side and keeps them live/accurate on
    # their own, no editing needed in between bot runs.
    daily_unix = int(daily_reset_dt.timestamp())
    weekly_unix = int(weekly_reset_dt.timestamp())

    value = (
        f"```ansi\n"
        f"\u001b[2;{cfg['ansi_color']}m# {current_time_str}\u001b[0m\n"
        f"```\n"
        f"• Daily reset <t:{daily_unix}:R>\n"
        f"• Weekly reset <t:{weekly_unix}:R>"
    )

    return {"name": region_name, "value": value, "inline": False}


def build_embed() -> dict:
    fields = [build_field(name, cfg) for name, cfg in REGIONS.items()]
    return {
        "title": "Server Status",
        "description": f"Members: {MEMBER_COUNT}",
        "color": 0x2B2D31,
        "fields": fields,
        "image": {"url": IMAGE_URL},
    }


# ----------------------------------------------------------------------
# DISCORD WEBHOOK CALLS
# ----------------------------------------------------------------------

def edit_message(message_id: str, embed: dict):
    url = f"{WEBHOOK_URL}/messages/{message_id}"
    resp = requests.patch(url, json={"embeds": [embed]})
    resp.raise_for_status()
    print(f"Edited message {message_id}")


def delete_message(message_id: str):
    url = f"{WEBHOOK_URL}/messages/{message_id}"
    resp = requests.delete(url)
    # 404 just means it was already gone — fine to ignore
    if resp.status_code not in (204, 404):
        resp.raise_for_status()
    print(f"Deleted message {message_id} (status {resp.status_code})")


def send_message(embed: dict) -> str:
    resp = requests.post(f"{WEBHOOK_URL}?wait=true", json={"embeds": [embed]})
    resp.raise_for_status()
    new_id = resp.json()["id"]
    print(f"Sent new message {new_id}")
    return new_id


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main():
    embed = build_embed()

    if MODE == "delete_resend":
        if MESSAGE_ID:
            delete_message(MESSAGE_ID)
        new_id = send_message(embed)
        # Print so you can grab it and store as MESSAGE_ID secret for next run.
        # See note below on auto-persisting this via GitHub Actions.
        print(f"::notice::NEW_MESSAGE_ID={new_id}")

    else:  # edit mode
        if not MESSAGE_ID:
            new_id = send_message(embed)
            print(f"::notice::NEW_MESSAGE_ID={new_id}")
        else:
            edit_message(MESSAGE_ID, embed)


if __name__ == "__main__":
    main()
