"""全功能服务（单进程、单容器）：自动发现 → 自动评估 → 自动上架 → 自动刷新 → 提供页面。

一个进程完成整条流水线，仍只用 Python 标准库：
  1. 启动时先跑一次：发现 → 评估 → 生成 → 提供页面；
  2. 按北京时间档位（默认 08:30 / 13:00 / 18:30）循环：
     app/discover.py（找线索，只记 needs_review）
     → app/evaluate.py（启发式打分；配了 AI_API_KEY + AI_MODEL 才调 AI）
     → app/promote.py（容易确定的自动上架，难确定的留待人工审核）
     → app/generate.py（重新生成页面，含自动上架区与待核实区）
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


STEP_TIMEOUT = int(os.environ.get("SERVICE_STEP_TIMEOUT", "1200"))


def run_step(name, script):
    print(f"[service] {name}", flush=True)
    try:
        subprocess.run([sys.executable, str(ROOT / "app" / script)],
                       check=False, timeout=STEP_TIMEOUT)
    except subprocess.TimeoutExpired:
        # 单步卡死（多半是外部站点不响应）不该拖死整轮：记一条，继续下一步。
        print(f"[service] {name} 超时（>{STEP_TIMEOUT}s），跳过", flush=True)


def refresh_cycle():
    run_step("discover", "discover.py")
    run_step("evaluate", "evaluate.py")
    run_step("promote", "promote.py")
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


class _DistHandler(SimpleHTTPRequestHandler):
    """只发文件，不列目录：目录没有 index 时也绝不把文件清单吐出去。"""

    def list_directory(self, path):
        self.send_error(403, "forbidden")
        return None


def first_cycle():
    try:
        refresh_cycle()
    except Exception as e:                      # 首轮失败不该让服务起不来
        print(f"[service] 首轮流水线出错：{type(e).__name__}: {e}", flush=True)


def main():
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    dist = ROOT / "dist"
    # 先把 HTTP 服务起起来，再在后台跑首轮流水线：
    # 首轮要抓 8 个源 + 可能调 AI，几十秒到几分钟，先服务能让健康检查立刻通过。
    dist.mkdir(parents=True, exist_ok=True)
    handler = partial(_DistHandler, directory=str(dist))
    server = ThreadingHTTPServer((host, port), handler)
    print(f"[service] serving {dist} on http://{host}:{port}", flush=True)
    threading.Thread(target=first_cycle, daemon=True).start()
    threading.Thread(target=loop, args=(parse_slots(),), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[service] stopped", flush=True)


if __name__ == "__main__":
    main()
