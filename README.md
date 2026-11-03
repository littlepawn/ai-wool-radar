<div align="center">
  <img src="assets/icon.svg" width="104" alt="AI 羊毛雷达">
  <h1>AI 羊毛雷达</h1>
  <p><strong>把国内外大厂的 AI 免费额度，核对成一张能筛选、能倒计时、能排序的表。</strong></p>
  <p>
    <img alt="Python" src="https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white">
    <img alt="Dependencies" src="https://img.shields.io/badge/dependencies-stdlib--only-0c7666">
    <img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white">
    <img alt="Tracking" src="https://img.shields.io/badge/tracking-27%20offers-b45309">
  </p>
</div>

![页面预览](docs/preview.png)

## 简介

AI 羊毛雷达（AI Wool Radar）是一份持续维护的 AI 免费额度清单：国内大厂的一次性发放照常追，
海外大厂本身就免费的常驻档单独立账，每日签到型、生图与生视频方案全部并入同一套到期监控。

当前收录 **27 条在追踪的活动 / 免费档**，覆盖 18 家厂商（国内 17 条、海外 10 条），
其中 8 条具备生图或生视频能力，交叉参考 11 个雷达与聚合信息源。

页面是**单个静态 HTML 文件**，不需要构建、不需要数据库、不依赖任何前端框架，双击或一个静态服务器就能打开。

> 数据口径：额度与截止日只写能在官方原文或官方文档里找到的内容；找不到就标「待核实」。
> 模型评分是编辑评分，不是厂商官方的基准跑分。

## 三条硬口径

1. **绑卡一票否决**：需要绑卡、验证支付方式、预充值，或必须先有付费余额才能用的，不进主列表。
   已剔除的条目在页面「争议与已排除」里留名并写原因（如 Cerebras、Pollinations）。
2. **评分分两层**：卡片右上角是这条羊毛的**综合分**（易薅 45% + 实用 55%，不含智力与额度）；
   点开「免费模型明细」才看每个**具体模型**的智力 / 额度 / 实用性分。
3. **入口只放核实过的页面**：有公开领取页的给跳转按钮；客户端内领取的只写步骤，不放假链接，
   API Base URL 不会被当成「去领取」的目标。

## 页面能做什么

| 能力 | 说明 |
|---|---|
| 搜索与筛选 | 按类型（限时 / 常驻免费 / 每日签到 / 客户端活动）、厂商、地区、能力（文本 / 生图 / 生视频）筛选 |
| 多种排序 | 即将到期、综合总分、最佳模型分、智力、额度、实用性、厂商 |
| 实时倒计时 | 固定截止日跑倒计时；每日 / 每月型跑重置倒计时，全部由同一个时间戳派生 |
| 模型评分榜 | 只排具体模型，不排平台泛称 |
| 到期监控台 | 固定截止、滚动到期、每日重置、长期监测四类集中在一张表 |
| 生图 / 生视频专栏 | 单独记录水印、商用授权、积分过期这些「暗规则」 |
| 争议与已排除 | 口径冲突、已下线、已被拉新占用、已剔除的活动集中留档 |
| 源健康度 | 11 个雷达源的新鲜度与借鉴点 |

## 快速开始

### 直接看

```sh
open index.html          # macOS
```

### 本地静态服务

```sh
python3 app/serve.py 8080     # 然后访问 http://localhost:8080
./run.sh                      # 等价写法，PORT 可覆盖
```

`app/serve.py` 只用 Python 标准库，并且**只对外暴露页面与图标**：
`app/`、`data/`、`state/` 和所有点文件一律返回 404，不会因为把仓库根目录当 docroot 而泄露源码或配置。

绑定地址默认 `0.0.0.0`，可用 `HOST` 限制到内网地址：

```sh
HOST=100.x.y.z PORT=5599 python3 app/serve.py
```

### Docker

```sh
cp .env.example .env      # 不配推送渠道也能只看页面
docker compose up --build -d
# 页面：http://localhost:8080
```

镜像基于 `python:3.12-slim`，非 root 用户运行，无第三方依赖。

## 巡检与推送

仓库同时保留一套零依赖的巡检工具链，用于发现官方页变化与临期提醒：

```sh
python3 app/check.py --dry-run   # 只打印发现，不写状态、不推送
python3 app/check.py             # 正式运行：写 state/seen.json，临期才推送
python3 app/scheduler.py         # 常驻进程，08:30 / 13:00 / 18:30 触发
```

去重规则：同一条临期只推一次；来源内容变化只记为「需人工核对」，不直接当成新活动；
抓取失败记为「待人工复核」，绝不等于「无活动」。

推送渠道全部走环境变量，完整清单见 [`.env.example`](.env.example)：

| 渠道 | 关键环境变量 |
|---|---|
| Bark | `BARK_URL` 或 `BARK_SERVER` + `BARK_KEY` |
| Server酱 Turbo | `SCT_SENDKEY` |
| Telegram | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` |
| 企业微信 | `WECOM_WEBHOOK_URL` |
| 飞书 | `FEISHU_WEBHOOK_URL` + `FEISHU_SECRET` |
| 钉钉 | `DINGTALK_WEBHOOK_URL` + `DINGTALK_SECRET` |
| ntfy / Gotify | `NTFY_URL` / `GOTIFY_URL` + `GOTIFY_TOKEN` |
| 邮件 SMTP | `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `SMTP_TO` |

正式推送前先演练（密钥自动打码，不发任何请求）：

```sh
python3 -m app.notify --dry-run --title "测试" --body "这是一条演练，不会真的发出去"
```

## 怎么维护

页面数据内联在 `index.html` 的 `ACTIVITIES` 数组里，一条活动一个对象：

```js
{id:"cf", region:"海外", vendor:"Cloudflare", title:"Workers AI 每日免费 Neurons",
 quota:"每日 10,000 Neurons", typeLabel:"每日型", cats:["daily","intl","evergreen"],
 mod:"文本 · 语音", deadline:null, reset:"daily", s:[4,5,5], steps:[...]}
```

| 字段 | 说明 |
|---|---|
| `id` | 唯一标识，排序与去重都靠它 |
| `region` / `vendor` | 地区与厂商，用于筛选 |
| `cats` | 可多选标签：`limited` / `evergreen` / `daily` / `intl` / `cn` / `media` / `client` |
| `deadline` | 固定截止日（ISO 8601，含时区）；没有就写 `null` |
| `reset` | `daily` / `monthly` / `null`，用于重置倒计时 |
| `s` | 具名模型的 `[智力, 额度, 实用性]`，各 1–5 分 |

改完直接刷新页面即可，无需构建。

**羊毛综合分** = 易薅 × 20 × 45% + 最值得用模型实用性 × 20 × 55%，满分 100。
没有具名模型时用活动级实用性代入，且不对平台泛称打分。

## 部署到 Linux（systemd）

`deploy/` 下提供三个示例单元，默认装在 `/opt/ai-wool`：

| 单元 | 作用 |
|---|---|
| `ai-wool-web.service` | 静态页面服务（默认只听 `127.0.0.1:8080`） |
| `ai-wool-check.service` | 一次性巡检（oneshot） |
| `ai-wool-check.timer` | 每天 08:30 / 13:00 / 18:30 触发巡检 |

```sh
sudo install -d /opt/ai-wool
sudo cp -a app data assets index.html run.sh /opt/ai-wool/
sudo cp deploy/ai-wool-*.service deploy/ai-wool-check.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai-wool-web.service ai-wool-check.timer
```

要经 Tailscale 内网访问，把 `ai-wool-web.service` 的 `HOST` 改成对应的 `100.x.y.z`，
不要直接暴露到公网。推送凭证放 `/etc/ai-wool.env`（权限 `600`），不进仓库。

## 目录结构

```text
.
├── index.html          # 页面本体（数据内联在 ACTIVITIES）
├── assets/             # 项目图标（svg + png）
├── docs/preview.png    # 页面预览图
├── app/
│   ├── serve.py        # 零依赖静态服务（白名单暴露）
│   ├── check.py        # 官方源变化 + 临期检测 + 去重推送
│   ├── notify.py       # 多渠道推送
│   ├── scheduler.py    # 定时循环
│   └── generate.py     # 旧版数据 → 页面生成器（备用）
├── data/               # offers.json / sources.json（备用生成链路）
├── deploy/             # systemd 示例
├── state/              # 巡检状态（不入库）
└── BUGS.md             # 历史问题与修复记录
```

## 安全

- `.env`、`state/`、`dist/` 已在 `.gitignore` 中排除。
- 推送模块只从环境变量读凭证，`--dry-run` 会对密钥打码。
- 巡检只访问公开页面，不登录、不代领、不绕过任何验证。
- `serve.py` 白名单放行页面与 `assets/`，其余路径一律 404。

## 已知问题

历史问题与修复记录见 [`BUGS.md`](BUGS.md)：泛称条目误评分、倒计时两种取整不一致、
领取按钮指向 API 地址等。

## 免责声明

本项目只汇总公开信息，不提供、不转售任何额度，也不保证活动长期有效。
额度、资格与截止时间最终以厂商官方页面为准。批量发放基本都要登录、实名、手动领取，
任何要求你交出厂商账号密码或主 API Key 去「自动薅」的工具都不要用。

## License

本项目暂未声明开源许可证。如需复用、分发或商业使用，请先联系作者。
