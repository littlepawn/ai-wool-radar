# 全功能版镜像：单容器、单进程、Python 标准库、无外部依赖。
# app/service.py 一个进程完成：自动发现 → 自动评估 → 自动刷新 → 提供页面。
# 基于 alpine + tzdata（检查器解析北京时间截止日需要时区数据）。
# 不复制 assets/：生成器在 assets 缺失时也能正常生成（图标按需复制），
# 仓库里已有的 assets/icon.*（README 项目 logo）不受影响、不被本镜像改动。
# 不改动仓库根目录的 index.html（2026-11-03 清理版快照），
# 生成产物只写容器内的 dist/（gitignored）。
FROM python:3.12-alpine
WORKDIR /app
COPY app/ ./app/
COPY data/ ./data/
RUN apk add --no-cache tzdata \
    && adduser -D appuser \
    && mkdir -p /app/dist /app/state \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 8080
CMD ["python", "app/service.py"]
