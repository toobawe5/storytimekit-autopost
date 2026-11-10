"""Decide whether a post is due right now. Standard library only, so it runs
in a couple of seconds before anything heavy is installed.

Writes `item=` and `slot=` to $GITHUB_OUTPUT (empty when nothing is due).

Rules:
- Each slot in config/schedule.json fires once per day, at or after its time,
  and no later than `late_limit_hours` after it (GitHub's timer can run late).
- For that slot it takes the queue item dated today for that slot, otherwise
  the first undated item in content/queue.json that hasn't been used yet.
"""
import argparse
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from common import log, posted, queue, schedule


def handled_ids(record):
    return {k for k, v in record.get("items", {}).items() if v.get("status") in ("posted", "partial", "rendered")}


def find_due(now=None):
    cfg = schedule()
    tz = ZoneInfo(cfg.get("timezone", "Asia/Karachi"))
    now = now or datetime.now(tz)
    late = timedelta(hours=float(cfg.get("late_limit_hours", 3)))
    record = posted()
    used = handled_ids(record)
    today = now.date().isoformat()
    items = queue()
    for slot, hhmm in sorted(cfg["slots"].items(), key=lambda kv: kv[1]):
        h, m = (int(x) for x in hhmm.split(":"))
        slot_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if not (slot_dt <= now <= slot_dt + late):
            continue
        key = f"{today}/{slot}"
        if key in record.get("slots", {}):
            continue
        dated = [q for q in items if q.get("date") == today and q.get("slot") == slot and q["id"] not in used]
        undated = [q for q in items if not q.get("date") and q["id"] not in used]
        pick = (dated or undated or [None])[0]
        if pick is None:
            log(f"Slot '{slot}' is due but the queue is empty — add posts to content/queue.json.")
            return None, slot
        return pick["id"], slot
    return None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--item", default="", help="force a specific queue item (manual run)")
    args = parser.parse_args()
    if args.item:
        item, slot = args.item, "manual"
    else:
        item, slot = find_due()
    log(f"due: item={item or '-'} slot={slot or '-'}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"item={item or ''}\nslot={slot or ''}\n")


if __name__ == "__main__":
    main()
