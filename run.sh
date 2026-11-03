#!/bin/sh
# 本地运行（不需要 Docker）：直接服务仓库根目录的 index.html。
# 若根目录没有 index.html，serve.py 会回退到 app/generate.py 生成的 dist/。
set -e
cd "$(dirname "$0")"
exec python3 app/serve.py "${PORT:-8080}"
