# 全功能版服务

单容器、单进程、零外部依赖，流水线是：

```
自动发现 → 自动评估 → 自动上架 → 自动刷新 → 提供页面
app/discover.py → app/evaluate.py → app/promote.py → app/generate.py → app/service.py 提供 dist/
                                                     ↘ app/check.py（来源对比 + 48h 临期提醒）
```

## 运行

```sh
# Docker（推荐）
docker compose up --build -d
# 页面：http://localhost:8080
# 日志：docker compose logs -f wool

# 本地（不需要 Docker）
chmod +x run.sh
./run.sh
```

档位默认北京时间 08:30 / 13:00 / 18:30，可用 `SERVICE_SLOTS` 改；
`PORT`（默认 8080）、`HOST`（默认 0.0.0.0）、`SERVICE_CHECK=0` 可跳过检查器。

## 自动发现（app/discover.py）

抓取 `data/sources.json` 里的公开页面，提取同时含免费信号和额度信号的
句子，写进 `state/candidates.json`，状态一律是 `needs_review`。
抓不到 JS 渲染页、网络失败只记 `fetch_failed`，绝不等于“无活动”；
不登录、不代领、不把聚合站说法直接当官方事实。

## 自动评估（app/evaluate.py）

- 默认启发式：从文本解析额度量级、模型档位词、领取摩擦词，
  给出智力 / 额度 / 实用性 / 易薅 1-5 分，`score_source=heuristic`。
- 可选 AI：`.env` 里同时配 `AI_API_KEY` + `AI_MODEL` 才启用，
  调 `AI_BASE_URL`（默认 OpenAI 官方地址）上 OpenAI 兼容的
  `/chat/completions` 接口；不配 Key 就静默跳过，只走启发式。
  AI 提示词由本项目设定（见 `app/evaluate.py` 的
  `AI_SYSTEM_PROMPT`）：只按线索文本打分，不编造额度、截止日、
  模型名；证据不足时分数写 null、置信度写 low；免费本身要求
  绑卡 / 绑支付方式 / 预充值时标记 `needs_card_binding=true`，
  按项目口径不进主列表。Key 只从环境变量读，绝不打印、不入库。

## 自动上架（app/promote.py）：容易确定的自动列，难确定的留给人

默认自动上架，只在难确定时留待人工审核。自动上架必须全部满足：
已评分、免费本身不绑卡、有明确额度信号（数字 + token/积分/credits/次/
万/亿其一）、易薅分 ≥ 3、不是纯工具类线索、置信度不是 low。
缺一条就留在待核实区，不自动列。

上架 ≠ 已核实：上架区卡片带“自动上架 · 未人工核实”标记，分数旁
标注 `heuristic` 或 `ai:<模型名>`，且不进主卡片的模型评分榜；
只有人工核对官方原文后，才可手工进入 `data/offers.json`。
没有 AI 时，启发式只能从“亿/万 tokens”这类可换算的量级里
确定额度，所以自动上架的面比较窄；配了 AI 后，AI 能判断
100 credits、每分钟 20 次这类量级，自动上架的面会变宽，
低置信的仍会留给人。

## 自动刷新与页面

`app/service.py` 在每个档位跑完发现、评估、生成、检查后，
页面自动更新；页面新增“自动发现 · 待核实”区，分数旁标注
`heuristic` 或 `ai:<模型名>`。**待核实线索不是已核实活动**：
只有人工核对官方原文后，才可手工进入 `data/offers.json`，
再由服务在下一档自动生成进主卡片。

## 保留与不改动的东西

- 仓库根目录 `index.html`（2026-11-03 清理版快照）：本服务不改动它，
  生成产物只写 `dist/index.html`（已进 `.gitignore`）。
- `README.md` 与 README 项目 logo（`assets/icon.*`）：重构不改动它们；
  生成器在 `assets/` 存在时才复制图标，缺失也不影响生成。
- 推送渠道：仍走 `.env`，见 `.env.example`；不填则只看页面、不推送。

## 旧入口去向

`app/serve.py`（只提供页面）与 `app/scheduler.py`（只跑检查器）
已被 `app/service.py` 取代，重构后应删除；原双服务
`docker-compose.yml` 已改为单服务 `wool`。
`deploy/` 下的 systemd 单元仍指向旧入口，如需继续用 systemd 部署，
请把执行命令改为 `python app/service.py`（本文件不擅自改动他人已提交的单元）。
