"""Render one queue item and post it.

    python src/run.py --item <id> --slot <slot> --mode review|live

review: render + put the video on a GitHub Release page, post nothing.
live:   render + Release + post to every platform in $PLATFORMS.
"""
import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from common import OUTPUT, env, fail, log, posted, products, queue, save_posted, schedule
from platforms import post_facebook, post_instagram, post_pinterest, post_youtube
from render import render_video


def text_for(item, platform):
    """Per-platform caption, falling back to the shared caption + hashtags."""
    custom = item.get(platform)
    if isinstance(custom, str) and custom.strip():
        return custom
    base = item.get("caption", "")
    tags = item.get("hashtags", "")
    return f"{base}\n\n{tags}".strip()


def make_release(item, files):
    """Put the day's video on a GitHub Release so it can be downloaded on a phone (for TikTok)."""
    if not env("GITHUB_ACTIONS"):
        log("(Not on GitHub — skipping the Release page.)")
        return None
    tag = f"post-{item['id']}"
    notes = (
        "TikTok caption (copy and paste):\n\n"
        f"{text_for(item, 'tiktok')}\n\n"
        "Download video.mp4 below and upload it in the TikTok app."
    )
    exists = subprocess.run(["gh", "release", "view", tag], capture_output=True).returncode == 0
    if exists:
        cmd = ["gh", "release", "upload", tag, *map(str, files), "--clobber"]
    else:
        cmd = ["gh", "release", "create", tag, *map(str, files), "--title", f"{item['id']} — {item.get('hook', '')}",
               "--notes", notes]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(f"(Could not create Release: {r.stderr.strip()[:300]})")
        return None
    url = subprocess.run(["gh", "release", "view", tag, "--json", "url", "-q", ".url"],
                         capture_output=True, text=True).stdout.strip()
    log(f"Release page: {url}")
    return url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--item", required=True)
    parser.add_argument("--slot", default="manual")
    parser.add_argument("--mode", default="review", choices=["review", "live"])
    args = parser.parse_args()

    item = next((q for q in queue() if q["id"] == args.item), None)
    if not item:
        fail(f"No post with id '{args.item}' in content/queue.json")
    product = products().get(item["product"])
    if not product:
        fail(f"Product '{item['product']}' is not in products/products.json")

    tz = ZoneInfo(schedule().get("timezone", "Asia/Karachi"))
    now = datetime.now(tz)
    out = OUTPUT / item["id"]
    shutil.rmtree(out, ignore_errors=True)
    files = render_video(product, item, out)
    release_url = make_release(item, [files["video"], files["thumbnail"], files["pin_cover"]])

    record = posted()
    entry = record["items"].setdefault(item["id"], {"results": {}})
    entry["release"] = release_url
    entry["updated"] = now.isoformat(timespec="minutes")
    if args.slot != "manual":
        record.setdefault("slots", {})[f"{now.date().isoformat()}/{args.slot}"] = item["id"]

    if args.mode == "review":
        if entry.get("status") not in ("posted", "partial"):
            entry["status"] = "rendered"
        save_posted(record)
        log("Review mode: video is ready on the Release page. Nothing was posted.")
        log(f"To publish it: Actions → Daily post → Run workflow → item = {item['id']}, mode = live")
        return

    wanted = [p.strip() for p in env("PLATFORMS", "instagram,facebook,youtube").split(",") if p.strip()]
    yt = item.get("youtube", {})
    pin = item.get("pinterest", {})
    jobs = {
        "instagram": lambda: post_instagram(files["video"], text_for(item, "instagram")),
        "facebook": lambda: post_facebook(files["video"], text_for(item, "facebook")),
        "youtube": lambda: post_youtube(
            files["video"], files["thumbnail"],
            yt.get("title") or item.get("hook", product["name"]),
            yt.get("description") or f"{text_for(item, 'youtube')}\n\n{product['etsy_url']}",
            yt.get("tags", [])),
        "pinterest": lambda: post_pinterest(
            files["video"], product.get("pinterest_board_id") or env("PINTEREST_DEFAULT_BOARD_ID"),
            pin.get("title") or product["name"], pin.get("description") or item.get("caption", ""),
            item.get("link") or product["etsy_url"]),
    }

    for name in wanted:
        if name not in jobs:
            log(f"Unknown platform '{name}' in PLATFORMS — skipping.")
            continue
        if entry["results"].get(name, {}).get("ok"):
            log(f"{name}: already posted earlier, skipping.")
            continue
        log(f"Posting to {name}…")
        res = jobs[name]()
        res["at"] = now.isoformat(timespec="minutes")
        entry["results"][name] = res
        log(f"  {name}: {'OK ' + (res.get('url') or '') if res['ok'] else 'FAILED — ' + res['error']}")

    oks = [n for n in wanted if entry["results"].get(n, {}).get("ok")]
    entry["status"] = "posted" if len(oks) == len(wanted) else ("partial" if oks else "failed")
    save_posted(record)
    log(f"Done: {entry['status']} ({len(oks)}/{len(wanted)} platforms).")
    if entry["status"] != "posted":
        sys.exit(1)  # makes GitHub email you that something failed


if __name__ == "__main__":
    main()
