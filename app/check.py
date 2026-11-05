"""Checker: re-fetch official/radar pages, hash comparable text, detect
new/changed/expiring-within-48h items, update state/seen.json, and only
then notify (dedupe: unchanged permanent tiers are never re-pushed).

Rules:
- A failed fetch (JS-rendered page, network error) is "待人工复核", never
  proof of "no activity".
- Expiry is computed from data/offers.json deadlines only; no deadline is
  invented. Relative deadlines (e.g. "31 days from claim") are not counted
  as a fixed 48h warning.
- --dry-run prints findings, writes no state, and sends no push.

Python stdlib only. Usage:
    python3 app/check.py [--dry-run] [--state state/seen.json]
    NOTIFY_DRY_RUN=1 python3 app/check.py
"""
import argparse
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFERS = ROOT / "data" / "offers.json"
SOURCES = ROOT / "data" / "sources.json"

try:
    from app.notify import send as notify_send
except ImportError:  # run as a plain script
    sys.path.insert(0, str(ROOT))
    from app.notify import send as notify_send


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ai-wool-radar-checker/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8", "replace")
    text = re.sub(r"<script.*?</script>", " ", raw, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_deadline(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        # 数据里的截止日全是北京时间；裸日期按 UTC 补会让临期判断差 8 小时。
        dt = dt.replace(tzinfo=timezone(timedelta(hours=8)))
    return dt


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--state", default=str(ROOT / "state" / "seen.json"))
    args = p.parse_args(argv)
    dry_run = args.dry_run or __import__("os").environ.get("NOTIFY_DRY_RUN") == "1"

    offers = json.loads(OFFERS.read_text(encoding="utf-8"))["offers"]
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))["sources"]
    state_path = Path(args.state)
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"hashes": {}, "notified": []}
    now = datetime.now(timezone.utc)
    findings = []

    for src in sources:
        try:
            digest = hashlib.sha256(fetch_text(src["url"]).encode("utf-8")).hexdigest()
        except Exception as e:
            findings.append(f"待人工复核：{src['name']} 抓取失败（{e}），不等于无活动")
            continue
        old = state["hashes"].get(src["id"])
        if old is None:
            findings.append(f"新来源已登记：{src['name']}（首次抓取，建立基线，不推送为新活动）")
        elif old != digest:
            findings.append(f"来源内容有变化：{src['name']}，需人工核对是否为新活动/规则变化")
        state["hashes"][src["id"]] = digest

    for o in offers:
        dt = parse_deadline(o.get("deadline"))
        if dt and timedelta(0) < dt - now <= timedelta(hours=48):
            key = f"expiry:{o['id']}"
            if key not in state["notified"]:
                findings.append(f"临期（48 小时内）：{o['vendor']} {o['name']} 截止 {o['deadline']}")
                state["notified"].append(key)

    # Findings that are "changed source / needs review" are NOT auto-pushed as
    # confirmed activities; only fixed-deadline expiry warnings are pushed,
    # and only once per offer (dedupe key above).
    push_lines = [f for f in findings if f.startswith("临期")]
    if push_lines:
        title = f"AI 羊毛临期提醒（{len(push_lines)} 条）"
        body = "\n".join(push_lines)
        if dry_run:
            print(f"[dry-run] would push: {title}\n{body}")
        else:
            try:
                for r in notify_send(title, body):
                    print(f"[{r['channel']}] ok={r['ok']} :: {r['detail']}")
            except Exception as e:
                # 推送炸了也要把 state 写下去，否则下次把同一条临期再推一遍。
                print(f"push failed: {type(e).__name__}: {e}", flush=True)
    else:
        print("无临期推送；其余发现仅记录/待人工复核：")
    for f in findings:
        print(" -", f)

    if not dry_run:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"state written: {state_path}")
    else:
        print("dry-run: state not written, nothing pushed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
