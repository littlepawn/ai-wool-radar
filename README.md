# AI 羊毛监控雷达（独立版）

一个**纯 Python 标准库、无外部依赖**的免费 AI 额度监控站：
数据只有一份（`data/offers.json`），生成器把它渲染成静态网页，
检查器定期抓取官方/雷达源做变化对比，只在“新变化 / 临期 48 小时内”
时才推送，且同一条临期只推一次。

> 本项目是原“AI 羊毛监控网页”的独立重构版，不改动原线上页面。
> 额度、截止日只写已核实内容，未核实一律标“待核实”，不编造。
> 不要把任何真实 Token / 密钥贴进代码、文档或聊天记录。

## 监控什么

- **国内大厂**：智谱 AutoClaw、阿里 Qoder / 百炼、腾讯 TokenHub、
  火山方舟、科大讯飞星火 MaaS、七牛云 Conatus、豆包签到、MiniMax 等。
- **海外大厂**：Cloudflare Workers AI（每日 10,000 Neurons，UTC 00:00 重置）、
  Agnes Flash（文本/生图/生视频）、Google AI Studio、Groq、OpenRouter `:free`
  （20 RPM / 每日 50 次）、NVIDIA Build、Hugging Face 等。
- **生图 / 生视频**：即梦、可灵、海螺、Leonardo、Firefly、PixVerse、Runway 等。
- **类型**：一次性领取、本身就免费（常驻）、每日/每月签到重置，三类分开筛选。

## 纳入标准：绑卡不纳入

**免费额度本身要求绑卡、绑支付方式验证或预充值的，不纳入。**
有付费升级选项、但免费层本身不用绑卡的，可以纳入（例如 OpenRouter
累计购买满 $10 只是提高上限，不是免费前提）。
被剔除的条目会在页面“争议与已排除”里留名并写原因，例如：

- Cerebras：免费层新增支付方式验证，已剔除；
- Pollinations：已改为 pollen 余额计费，已剔除；
- GitHub Models：已于 2026-07-30 退役，已剔除。

## 评分公式（编辑评分，非官方）

- **具体模型分**：智力 / 额度 / 实用性各 1–5 分。
  只有具名模型才有模型分；“平台内各语言模型（逐个领）”这类泛称
  **不打模型分**（见 `BUGS.md` 第 1 条）。
- **羊毛总分（卡片右上角）**：易薅 45% + 实用 55%，满分 100 分。
  公式：`易薅×20×0.45 + 最值得用模型实用性×20×0.55`
  （无具名模型时用活动级实用性代入，并在数据里注明）。
  易薅看领取摩擦（注册即用 5 分、每日手动领/客户端 3 分、多步迁移或有争议 2 分等）；
  实用看额度好不好用、有无水印/商用限制等。
- **到期监控**：固定截止日跑倒计时（页面上所有倒计时都由同一个
  `data-deadline` 时间戳派生，不会出现“59 天”和“58 天 14:39”两种取整）；
  每日/每月型跑重置提示；无固定截止日只写“无固定截止日”，不编造日期。

## 目录结构

```
app/generate.py   # 从 offers.json 生成 dist/index.html（唯一渲染入口）
app/check.py      # 抓取对比 + 48h 临期检测 + 去重推送
app/notify.py     # 推送模块（见下）
app/serve.py      # 静态服务器（启动时若缺 dist 则先生成）
app/scheduler.py  # 检查器定时循环：08:30 / 13:00 / 18:30 Asia/Shanghai
data/offers.json  # 唯一事实源：活动、额度、截止日、模型分、争议、已排除
data/sources.json # 检查器抓取的官方/雷达源列表
state/seen.json   # 检查器状态（已忽略，不进 Git）
dist/index.html   # 生成产物（已忽略，不进 Git）
```

## 本地运行（不需要 Docker）

```sh
chmod +x run.sh
./run.sh            # 生成页面并在 http://localhost:8080 提供服务
# 或手动：
python3 app/generate.py
python3 app/serve.py 8080
```

## Docker 运行

```sh
cp .env.example .env    # 按需填推送渠道（见下），不填则只看页面、不推送
docker compose up --build -d
# 页面：http://localhost:8080
# 只起页面服务：docker compose up --build -d web
```

部署方式说明（已选定，不含糊）：`docker-compose.yml` 是**两个服务**——
`web` 只服务页面，`checker` 只跑 `app/scheduler.py` 定时检查。
单服务替代方案：只起 `web`，并用宿主机 cron 在约 08:30 / 13:00 / 18:30
执行 `docker compose run --rm checker python app/check.py`。
镜像基于 `python:3.12-slim`、非 root 用户运行，Python 标准库，无外部依赖。

## 检查器

```sh
python3 app/check.py --dry-run   # 只打印发现，不写状态、不推送
python3 app/check.py             # 正式跑：写 state/seen.json，临期才推送
NOTIFY_DRY_RUN=1 python3 app/check.py
```

去重规则：同一条临期（`expiry:<offer-id>`）只推一次；
来源内容变化只记为“需人工核对”，不直接当成“新活动”推送；
抓取失败记为“待人工复核”，绝不等于“无活动”；
未变的常驻免费层不重复推送。

## 推送配置（全部只用环境变量）

先演练，再开启真实推送：

```sh
python3 -m app.notify --dry-run --title "测试" --body "这是一条演练，不会真的发出去"
python3 -m app.notify --dry-run --only bark,telegram --title "测试" --body "演练"
```

| 渠道 | 关键环境变量 |
|---|---|
| Bark | `BARK_URL` 或 `BARK_SERVER` + `BARK_KEY` |
| Server酱 Turbo | `SCT_SENDKEY` |
| PushPlus | `PUSHPLUS_TOKEN` |
| 企业微信群机器人 | `WECOM_WEBHOOK_URL` |
| 钉钉群机器人（签名） | `DINGTALK_WEBHOOK_URL` + `DINGTALK_SECRET` |
| 飞书群机器人（签名） | `FEISHU_WEBHOOK_URL` + `FEISHU_SECRET` |
| Telegram Bot | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` |
| ntfy | `NTFY_URL`（话题地址），可选 `NTFY_TOKEN` |
| Gotify | `GOTIFY_URL` + `GOTIFY_TOKEN` |
| Discord Webhook | `DISCORD_WEBHOOK_URL` |
| Slack Webhook | `SLACK_WEBHOOK_URL` |
| 邮件 SMTP | `SMTP_HOST` / `SMTP_PORT` / `SMTP_TLS` / `SMTP_USER` / `SMTP_PASS` / `SMTP_FROM` / `SMTP_TO` |
| 通用 Webhook | `WEBHOOK_URL`，可选 `WEBHOOK_TOKEN` |
| WxPusher | `WXPUSHER_APP_TOKEN` + `WXPUSHER_UIDS`（英文逗号分隔） |
| PushDeer | `PUSHDEER_KEY`，可选 `PUSHDEER_SERVER` |

实现约定（`app/notify.py`）：`send(title, body, url)` 统一入口，
每个渠道一个独立小函数；某个渠道失败不阻塞其他渠道；
`--dry-run` 只打印“会发什么”（密钥已打码），不发任何请求。

## 推到 GitHub（只给命令，不执行）

由仓库主人自己决定仓库名与可见性（公开/私有），本项目不替你选，
也不要求你在聊天里贴任何 Token：

```sh
cd ai-wool-radar
git init
git add .
git commit -m "AI 羊毛监控雷达：独立重构版"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

> 注意：`git push` 需要你本人在 GitHub 上先建好同名空仓库；
> `.env` 与 `state/` 已在 `.gitignore` 里，不会被提交。
> 如果你在浏览器里登录 GitHub，请在浏览器接管流程中自己完成登录，
> 不要把密码或 Token 发给任何对话方。
