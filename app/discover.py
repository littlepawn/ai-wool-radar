"""自动发现：抓取 data/sources.json 里的公开页面，找出疑似新免费活动的线索。

只做线索收集，不做结论：
- 每个线索都标 status="needs_review"，必须经人工（或 AI 辅助 + 人工）核对
  官方原文后，才有资格进入 data/offers.json 的已核实列表。
- 抓不到正文的 JS 渲染页、网络失败，只记为 fetch_failed，绝不等于“无活动”。
- 不登录、不代领、不绕过任何验证；不把聚合站的说法直接当成官方事实。
- 发现结果写 state/candidates.json（已进 .gitignore），不直接改 offers.json。

用法：
    python3 app/discover.py [--dry-run] [--state state/candidates.json]
"""

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "data" / "sources.json"
TZ = timezone(timedelta(hours=8))

# 只要同时沾到“免费信号”和“额度信号”的句子才算一条线索，避免整页噪音。
FREE_WORDS = ("免费", "free", "额度", "token", "Token", "邀请码", "invite")
QUOTA_WORDS = ("亿", "万", "tokens", "Tokens", "credits", "积分", "时长", "小时")


def fetch_text(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "ai-wool-radar-discover/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8", "replace")
    text = re.sub(r"<script.*?</script>", " ", raw, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_snippets(text, limit=5):
    # 按句号/换行切分，取同时含免费信号和额度信号的句子，截断到 200 字。
    parts = re.split(r"[。！？\n]", text)
    out = []
    for p in parts:
        p = p.strip()
        if len(p) < 20 or len(p) > 500:
            continue
        if any(w in p for w in FREE_WORDS) and any(w in p for w in QUOTA_WORDS):
            out.append(p[:200])
        if len(out) >= limit:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--state", default=str(ROOT / "state" / "candidates.json"))
    args = ap.parse_args()

    try:
        sources = json.loads(SOURCES.read_text(encoding="utf-8")).get("sources", [])
    except Exception as e:
        print(f"discover: cannot read sources.json: {e}", flush=True)
        return 1

    state_path = Path(args.state)
    old = {}
    if state_path.exists():
        try:
            old = {c["id"]: c for c in json.loads(state_path.read_text(encoding="utf-8")).get("candidates", [])}
        except Exception:
            old = {}
    now = datetime.now(TZ).isoformat(timespec="seconds")
    found, failed = [], []
    for s in sources:
        try:
            snippets = extract_snippets(fetch_text(s["url"]))
        except Exception as e:
            failed.append({"source": s["id"], "error": type(e).__name__})
            continue
        for snip in snippets:
            cid = hashlib.sha256(f"{s['id']}|{snip}".encode()).hexdigest()[:16]
            if cid in old:
                old[cid]["last_seen"] = now
                continue
            found.append({
                "id": cid, "source": s["id"], "source_name": s.get("name", s["id"]),
                "url": s["url"], "snippet": snip, "first_seen": now, "last_seen": now,
                "status": "needs_review", "score": None, "score_source": None,
            })
    merged = list(old.values()) + found
    merged.sort(key=lambda c: c.get("first_seen", ""), reverse=True)
    print(f"discover: {len(found)} new, {len(failed)} fetch_failed, "
          f"{len(merged)} total candidates", flush=True)
    for f in failed:
        print(f"  fetch_failed: {f['source']} ({f['error']})", flush=True)
    if args.dry_run:
        for c in found:
            print(f"  new: [{c['source']}] {c['snippet'][:120]}", flush=True)
        return 0
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"candidates": merged[:200]}, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    print(f"discover: wrote {state_path} ({len(merged[:200])} candidates)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
