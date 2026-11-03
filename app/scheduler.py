"""Scheduler for the checker service: run app/check.py at about
08:30, 13:00 and 18:30 Asia/Shanghai every day.

Uses only the stdlib (zoneinfo) so the slim Docker image needs no cron
daemon. If the process restarts, it simply waits for the next slot.

Usage: python3 app/scheduler.py
Env: CHECK_DRY_RUN=1 for a dry-run checker pass (no state write, no push).
"""
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
SLOTS = [(8, 30), (13, 0), (18, 30)]
TZ = ZoneInfo("Asia/Shanghai")


def next_slot(now):
    for h, m in SLOTS:
        cand = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if cand > now:
            return cand
    nxt = now + timedelta(days=1)
    return nxt.replace(hour=SLOTS[0][0], minute=SLOTS[0][1], second=0, microsecond=0)


def main():
    print("scheduler started; slots (Asia/Shanghai): 08:30, 13:00, 18:30", flush=True)
    while True:
        now = datetime.now(TZ)
        target = next_slot(now)
        wait = (target - now).total_seconds()
        print(f"next check at {target.isoformat()} (in {wait/60:.0f} min)", flush=True)
        time.sleep(wait)
        env = dict(os.environ)
        if os.environ.get("CHECK_DRY_RUN"):
            env["NOTIFY_DRY_RUN"] = "1"
        subprocess.run([sys.executable, str(ROOT / "app" / "check.py")], env=env, check=False)


if __name__ == "__main__":
    main()
