#!/bin/sh
# 本地运行全功能版（不需要 Docker）：发现 → 评估 → 生成 → 提供页面。
set -e
cd "$(dirname "$0")"
exec python3 app/service.py
