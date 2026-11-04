# 轻量版服务

一个容器、一个进程、零外部依赖：`app/light.py` 既生成页面、又提供页面，
还按北京时间 08:30 / 13:00 / 18:30 定时重新生成并跑检查器。
它是对原有 web + checker 双服务方案的轻量替代，不是替换仓库根目录的
清理版 `index.html`（那是 2026-11-03 的静态快照，本服务不改动它；
生成产物只写 `dist/index.html`，已进 `.gitignore`）。

## Docker 运行（推荐）

```sh
docker compose -f docker-compose.light.yml up --build -d
# 页面：http://localhost:8080
# 查看日志：docker compose -f docker-compose.light.yml logs -f wool
# 停止：docker compose -f docker-compose.light.yml down
```

## 本地运行（不需要 Docker）

```sh
chmod +x run-light.sh
./run-light.sh
# 或：python3 app/light.py
```

## 环境变量

- `PORT`：监听端口，默认 8080
- `HOST`：监听地址，默认 0.0.0.0
- `LIGHT_SLOTS`：刷新档位，默认 `08:30,13:00,18:30`
- `LIGHT_CHECK`：设为 `0` 则只重新生成、不跑检查器
- 推送渠道（临期 48 小时内才推）：仍走 `.env`，见 `.env.example`；
  不填则只看页面、不推送

## 轻在哪

- 1 个容器、1 个进程，替代原来的 web + checker 两个服务
- 基础镜像 `python:3.12-alpine` + `tzdata`，无 pip 依赖
- 不用容器内 cron：档位等待用标准库线程实现
- 不复制 `assets/`：轻量版生成器不需要它，构建不会因缺失而失败

## 它做不到的事（说清楚）

- 不会自动“发明”新活动：页面数据唯一来源仍是 `data/offers.json`，
  检查器只做来源变化对比和临期提醒；新活动核实后需人工更新
  `data/offers.json`，服务会在下一个档位自动重新生成页面。
- 不自动把页面推到 GitHub Pages 或覆盖根目录 `index.html`：
  如需发布新版，仍按仓库原有流程处理。
