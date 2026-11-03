#!/bin/sh
# 本地运行（不需要 Docker）：生成页面并启动静态服务器。
set -e
cd "$(dirname "$0")"
python3 app/generate.py
exec python3 app/serve.py "${PORT:-8080}"
