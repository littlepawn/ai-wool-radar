"""全功能服务（单进程、单容器）：自动发现 → 自动评估 → 自动刷新 → 提供页面。

一个进程完成整条流水线，仍只用 Python 标准库：
  1. 启动时先跑一次：发现 → 评估 → 生成 → 提供页面；
  2. 按北京时间档位（默认 08:30 / 13:00 / 18:30）循环：
     app/discover.py（找线索，只记 needs_review）
     → app/evaluate.py（启发式打分；配了 AI_API_KEY + AI_MODEL 才调 AI）
     → app/generate.py（重新生成页面，含“自动发现 · 待核实”区）
     → app/check.py（来源变化对比 + 48 小时临期提醒，见原有规则）。

关键边界（不要跨过）：
- 自动发现 ≠ 自动上架：线索在页面上只出现在“待核实”区，
  必须经人工核对官方原文后，才可手工进入 data/offers.json 的已核实列表。
- 自动评估 ≠ 官方评分：分数旁会标注 heuristic 或 ai:<模型>，
  未核实前一律不进主卡片的模型评分榜。
- AI 是可选项：不配 Key 也能全程跑，只是全部走启发式评分。

用法：python3 app/service.py
环境变量：PORT（默认 8080）、HOST（默认 0.0.0.0）、
  SERVICE_SLOTS（默认 "08:30,13:00,18:30"）、SERVICE_CHECK（0 则跳过检查器）、
  AI_API_KEY / AI_BASE_URL / AI_MODEL（见 app/evaluate.py）。
"""

import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TZ = timezone(timedelta(hours=8))  # 北京时间，无夏令时，固定 +08:00 即准确


def parse_slots():
    slots = []
    for part in os.environ.get("SERVICE_SLOTS", "08:30,13:00,18:30").split(","):
        part = part.strip()
        if not part:
            continue
        h, m = part.split(":")
        slots.append((int(h), int(m)))
    return sorted(set(slots)) or [(8, 30), (13, 0), (18, 30)]


def next_slot(now, slots):
    for h, m in slots:
        cand = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if cand > now:
            return cand
    nxt = now + timedelta(days=1)
    return nxt.replace(hour=slots[0][0], minute=slots[0][1], second=0, microsecond=0)


def run_step(name, script):
    print(f"[service] {name}", flush=True)
    subprocess.run([sys.executable, str(ROOT / "app" / script)], check=False)


def refresh_cycle():
    run_step("discover", "discover.py")
    run_step("evaluate", "evaluate.py")
    run_step("generate", "generate.py")
    if os.environ.get("SERVICE_CHECK", "1") != "0":
        run_step("check", "check.py")


def loop(slots):
    while True:
        now = datetime.now(TZ)
        target = next_slot(now, slots)
        wait = (target - now).total_seconds()
        print(f"[service] next refresh at {target.isoformat()} (in {wait / 60:.0f} min)", flush=True)
        time.sleep(wait)
        refresh_cycle()


def main():
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    dist = ROOT / "dist"
    refresh_cycle()
    dist.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=loop, args=(parse_slots(),), daemon=True).start()
    handler = partial(SimpleHTTPRequestHandler, directory=str(dist))
    server = ThreadingHTTPServer((host, port), handler)
    print(f"[service] serving {dist} on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[service] stopped", flush=True)


if __name__ == "__main__":
    main()
