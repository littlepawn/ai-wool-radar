"""轻量版服务：一个进程 = 生成页面 + 提供页面 + 定时检查。

只用 Python 标准库，无外部依赖，无 cron 守护进程，无第二个容器。
启动时先生成一次页面，随后在后台线程里按北京时间档位
（默认 08:30 / 13:00 / 18:30）重复：重新生成页面，再跑一次检查器。

注意它不“发明”新活动：页面数据唯一来源仍是 data/offers.json，
检查器只做来源变化对比和 48 小时临期提醒；新活动核实后需要
人工更新 offers.json，再由本服务在下一个档位自动重新生成。
它也不改动仓库根目录的 index.html（那是 2026-11-03 的清理版快照），
生成产物只写 dist/index.html（已进 .gitignore）。

用法：
    python3 app/light.py
环境变量：
    PORT         监听端口，默认 8080
    HOST         监听地址，默认 0.0.0.0
    LIGHT_SLOTS  档位，逗号分隔，默认 "08:30,13:00,18:30"（北京时间）
    LIGHT_CHECK  设为 0 则只重新生成、不跑检查器，默认跑检查器
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
    for part in os.environ.get("LIGHT_SLOTS", "08:30,13:00,18:30").split(","):
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


def regenerate():
    print("[light] regenerate dist/index.html", flush=True)
    subprocess.run([sys.executable, str(ROOT / "app" / "generate.py")], check=False)


def run_check():
    if os.environ.get("LIGHT_CHECK", "1") == "0":
        return
    print("[light] run app/check.py", flush=True)
    subprocess.run([sys.executable, str(ROOT / "app" / "check.py")], check=False)


def loop(slots):
    while True:
        now = datetime.now(TZ)
        target = next_slot(now, slots)
        wait = (target - now).total_seconds()
        print(f"[light] next refresh at {target.isoformat()} (in {wait / 60:.0f} min)", flush=True)
        time.sleep(wait)
        regenerate()
        run_check()


def main():
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    dist = ROOT / "dist"
    regenerate()
    dist.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=loop, args=(parse_slots(),), daemon=True).start()
    handler = partial(SimpleHTTPRequestHandler, directory=str(dist))
    server = ThreadingHTTPServer((host, port), handler)
    print(f"[light] serving {dist} on http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[light] stopped", flush=True)


if __name__ == "__main__":
    main()
