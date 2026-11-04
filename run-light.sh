#!/bin/sh
# 本地运行轻量版（不需要 Docker）：生成页面、提供页面、定时刷新。
set -e
cd "$(dirname "$0")"
exec python3 app/light.py
