"""Build a static index.html from data/offers.json (single source of truth).

Rules enforced here (see BUGS.md):
- Only named models get model scores. A generic platform entry (generic_note
  present) must have no model scores.
- A "go claim" link must be a verified registration/console page, never an
  API base URL or a docs page masquerading as a claim page.
- Each offer has at most one deadline; the page shows expiry only from that
  single timestamp (the JS countdown derives days+time from one value).
- Scores are computed once, here, not re-computed in the browser.

Python stdlib only. Usage: python3 app/generate.py [--out dist/index.html]
"""
import json
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "offers.json"
SOURCES = ROOT / "data" / "sources.json"
ASSETS = ROOT / "assets"
OUT_DEFAULT = ROOT / "dist" / "index.html"

# Known non-claim URLs that must never be labelled "去领取".
FORBIDDEN_CLAIM_URLS = (
    "apihub.agnes-ai.com",
    "/v1",  # bare API base URLs
)


def wool_total(offer):
    """Ease 45% + best-model practicality 55% (offer practicality if no named model)."""
    ease = offer.get("ease")
    if ease is None:
        return None
    models = offer.get("models") or []
    prac = max((m["practicality"] for m in models), default=None)
    if prac is None:
        prac = offer.get("practicality")
    if prac is None:
        return None
    return round(ease * 20 * 0.45 + prac * 20 * 0.55)


def validate(data):
    offers = data["offers"]
    seen = set()
    for o in offers:
        assert o["id"] not in seen, f"duplicate id: {o['id']}"
        seen.add(o["id"])
        assert o["region"] in ("domestic", "overseas")
        assert o["category"] in ("text", "image", "video")
        assert o["kind"] in ("one_time", "permanent", "daily", "monthly")
        assert 1 <= o["ease"] <= 5, o["id"]
        assert 1 <= o["practicality"] <= 5, o["id"]
        if o.get("generic_note"):
            assert not o.get("models"), f"generic entry must not carry model scores: {o['id']}"
        for m in o.get("models") or []:
            assert m["name"] and "平台内" not in m["name"], f"generic model name: {o['id']}"
            for k in ("intelligence", "quota", "practicality"):
                assert 1 <= m[k] <= 5, f"{o['id']} {m['name']}"
        if o.get("link_label") == "去领取":
            assert o.get("link"), f"claim link missing: {o['id']}"
            assert not any(bad in o["link"] for bad in FORBIDDEN_CLAIM_URLS), \
                f"claim link must not be an API base URL: {o['id']}"
    return offers


def iso_local(value):
    """把 data-deadline 用的 ISO 串统一成 +0800 形式。

    Safari/iOS 对 "+08:00" 这种带冒号的偏移会返回 Invalid Date，
    倒计时就会显示成 NaN；"+0800" 两家都认。
    """
    return str(value).replace("+08:00", "+0800")


def render_card(o):
    total = o["wool_total"]
    badge = f'<span class="wool-score" title="易薅 45% + 实用 55%">易薅·实用 {total}</span>' \
        if total is not None else '<span class="wool-score muted">未评分</span>'
    deadline_attr = f' data-deadline="{escape(iso_local(o["deadline"]))}"' if o.get("deadline") else ""
    deadline_text = ""
    if o.get("deadline"):
        deadline_text = f'<p class="expiry" data-expiry{deadline_attr}>' \
            f'截止 {escape(o["deadline"][:10])} · <span class="countdown">计算中…</span></p>'
    elif o.get("reset") == "daily":
        deadline_text = '<p class="expiry">每日重置 · 以官方页为准</p>'
    elif o.get("reset") == "monthly":
        deadline_text = '<p class="expiry">每月重置 · 以官方页为准</p>'
    else:
        deadline_text = '<p class="expiry">无固定截止日 · 以官方页为准</p>'
    if o.get("models"):
        rows = "".join(
            f'<li><b>{escape(m["name"])}</b> '
            f'智力 {m["intelligence"]} · 额度 {m["quota"]} · 实用 {m["practicality"]}</li>'
            for m in o["models"]
        )
        dropdown = f'<details class="model-dropdown"><summary>免费模型明细 · ' \
            f'{len(o["models"])} 个（点开看每个模型的评分）</summary><ul>{rows}</ul></details>'
    else:
        note = escape(o.get("generic_note") or "按官方页各模型为准，不对平台泛称打模型分")
        dropdown = f'<details class="model-dropdown"><summary>免费模型明细</summary>' \
            f'<p class="muted">{note}</p></details>'
    link = ""
    if o.get("link"):
        link = f'<a class="claim" href="{escape(o["link"])}" target="_blank" rel="noopener">' \
            f'{escape(o.get("link_label") or "去领取")} ↗</a>'
    else:
        link = f'<span class="claim muted">{escape(o.get("link_label") or "平台内领取")}</span>'
    steps = "".join(f"<li>{escape(s)}</li>" for s in o["claim_steps"])
    steps_text = "；".join(o["claim_steps"]).replace('"', "")
    ver = escape(o.get("verification") or "")
    return f"""
<article class="card" data-region="{o["region"]}" data-category="{o["category"]}"
  data-kind="{o["kind"]}" data-total="{total if total is not None else -1}"
  data-deadline="{escape(iso_local(o.get("deadline") or "9999"))}"
  data-name="{escape(o["name"])}">
  <div class="card-top"><span class="tag">{escape(o["vendor"])} · {'国内' if o["region"] == 'domestic' else '海外'}</span>{badge}</div>
  <h2>{escape(o["name"])}</h2>
  <p class="quota">{escape(o["quota"])}</p>
  <p class="muted">类型：{'文本' if o["category"] == 'text' else '生图' if o["category"] == 'image' else '生视频'} · {escape(ver)}</p>
  {deadline_text}
  <p class="muted">{escape(o.get("notes") or "")}</p>
  {dropdown}
  <details><summary>领取 / 接入步骤</summary><ol>{steps}</ol></details>
  <p>{link}</p>
  <p><button class="btn copy-btn" type="button" data-steps="{escape(steps_text)}">复制领取步骤</button>
  <button class="btn follow-btn" type="button" data-id="{escape(o["id"])}">关注到期</button></p>
</article>"""


def main():
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else OUT_DEFAULT
    data = json.loads(DATA.read_text(encoding="utf-8"))
    offers = validate(data)
    for o in offers:
        o["wool_total"] = wool_total(o)
    cards = "\n".join(render_card(o) for o in offers)
    disputed = "\n".join(
        f'<li><b>{escape(d["title"])}</b>：{escape(d["detail"])}</li>'
        for d in data.get("disputed", [])
    )
    excluded = "\n".join(
        f'<li><b>{escape(e["id"])}</b>：{escape(e["reason"])}</li>'
        for e in data.get("excluded", [])
    )
    model_board = []
    for o in offers:
        for m in o.get("models") or []:
            model_board.append((m["intelligence"] + m["quota"] + m["practicality"], m, o))
    model_board.sort(key=lambda x: -x[0])
    board = "\n".join(
        f'<li>{escape(m["name"])}（{escape(o["vendor"])}）'
        f' 智力 {m["intelligence"]} · 额度 {m["quota"]} · 实用 {m["practicality"]}</li>'
        for _, m, o in model_board[:10]
    )
    # 到期监控台：固定截止日（按时间排）、每日重置、每月重置、无固定截止日。
    fixed = sorted((o for o in offers if o.get("deadline")),
                   key=lambda o: o["deadline"])
    desk_fixed = "".join(
        f'<li><b>{escape(o["vendor"])} {escape(o["name"])}</b> '
        f'<span class="expiry" data-expiry data-deadline="{escape(iso_local(o["deadline"]))}">'
        f'截止 {escape(o["deadline"][:10])} · <span class="countdown">计算中…</span></span></li>'
        for o in fixed) or "<li>暂无固定截止日活动</li>"
    desk_daily = "".join(
        f"<li>{escape(o['vendor'])} {escape(o['name'])}（每日重置）</li>"
        for o in offers if o.get("reset") == "daily") or "<li>暂无</li>"
    desk_monthly = "".join(
        f"<li>{escape(o['vendor'])} {escape(o['name'])}（每月重置）</li>"
        for o in offers if o.get("reset") == "monthly") or "<li>暂无</li>"
    desk_open = "".join(
        f"<li>{escape(o['vendor'])} {escape(o['name'])}</li>"
        for o in offers if not o.get("deadline") and o.get("reset") not in ("daily", "monthly")
    ) or "<li>暂无</li>"
    sources = []
    try:
        sources = json.loads(SOURCES.read_text(encoding="utf-8")).get("sources", [])
    except Exception:
        sources = []
    sources_html = "".join(
        f'<li><a href="{escape(s["url"])}" target="_blank" rel="noopener">{escape(s["name"])}</a></li>'
        for s in sources) or "<li>暂无</li>"
    # 自动发现区：只展示待核实线索，绝不冒充已核实活动；分数旁标注来源。
    candidates_html = "<li>暂无新线索</li>"
    try:
        cands = json.loads((ROOT / "state" / "candidates.json").read_text(encoding="utf-8")).get("candidates", [])
    except Exception:
        cands = []
    # 自动上架区与待核实区用同一批线索、按 status 分流展示。
    auto_cands = [c for c in cands if c.get("status") == "auto_listed"]
    cands = [c for c in cands if c.get("status") != "auto_listed"]
    auto_html = "<li>暂无自动上架线索</li>"
    if auto_cands:
        auto_items = []
        for c in auto_cands[:20]:
            sc = c.get("score") or {}
            def _s2(k):
                v = sc.get(k)
                return "—" if v is None else str(v)
            auto_items.append(
                f'<li><b>自动上架 · 未人工核实</b> '
                f'{escape(c.get("source_name", c.get("source", "")))}：'
                f'{escape(c.get("snippet", ""))} '
                f'智力 {_s2("intelligence")} · 额度 {_s2("quota")} · '
                f'实用 {_s2("practicality")} · 易薅 {_s2("ease")} '
                f'（{escape(str(c.get("score_source") or "未评分"))}） '
                f'<a href="{escape(c.get("url", ""))}" target="_blank" rel="noopener">看来源</a></li>')
        auto_html = "".join(auto_items)
    if cands:
        items = []
        for c in cands[:20]:
            sc = c.get("score") or {}
            score_txt = ""
            if sc:
                def _s(k):
                    v = sc.get(k)
                    return "—" if v is None else str(v)
                score_txt = (f" 智力 {_s('intelligence')} · 额度 {_s('quota')} · "
                             f"实用 {_s('practicality')} · 易薅 {_s('ease')} "
                             f"（{escape(str(c.get('score_source') or '未评分'))}，"
                             f"置信度 {escape(str(sc.get('confidence') or '—'))}）")
            items.append(
                f'<li><b>{escape(c.get("source_name", c.get("source", "")))}</b>：'
                f'{escape(c.get("snippet", ""))}{score_txt} '
                f'<a href="{escape(c.get("url", ""))}" target="_blank" rel="noopener">看来源</a> '
                f'<span class="muted">首次发现 {escape(str(c.get("first_seen", ""))[:10])}</span></li>')
        candidates_html = "".join(items)
    n_dom = sum(1 for o in offers if o["region"] == "domestic")
    n_over = sum(1 for o in offers if o["region"] == "overseas")
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="每日巡检官方页面的 AI 免费额度雷达：额度、截止日与模型评分只有一份事实源。">
<meta name="theme-color" content="#0b1220">
<link rel="icon" type="image/svg+xml" href="icon.svg">
<link rel="apple-touch-icon" href="icon-128.png">
<title>AI 羊毛雷达</title>
<style>
:root{{color-scheme:light}}
*{{box-sizing:border-box}}
body{{font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;margin:0;background:#f4f6f3;color:#17211c;line-height:1.65}}
.wrap{{max-width:1080px;margin:0 auto;padding:20px 16px 48px}}
.pill{{display:inline-block;background:#fff;border:1px solid #d8ddd6;border-radius:999px;padding:6px 14px;margin:4px 6px 4px 0;font-size:14px}}
.pill b{{color:#0f766e}}
.hero{{background:linear-gradient(180deg,#eef5ee,#f4f6f3);border-radius:24px;padding:28px 8px 8px}}
.hero h1{{font-family:Georgia,"Songti SC",serif;font-size:52px;line-height:1.15;margin:14px 0}}
.hero h1 em{{font-style:normal;color:#0f766e}}
.hero p{{font-size:17px;color:#42524a;max-width:760px}}
.conclusion{{background:#fff;border-left:6px solid #0f766e;border-radius:16px;box-shadow:0 8px 30px rgba(20,40,30,.08);padding:20px 22px;margin:20px 0}}
.conclusion h2{{margin:0 0 8px;font-size:15px}}
.conclusion h2 span{{background:#0f766e;color:#fff;border-radius:999px;padding:4px 14px}}
.filters{{background:#fff;border:1px solid #dfe5df;border-radius:16px;padding:14px;display:flex;flex-wrap:wrap;gap:10px;align-items:center;position:sticky;top:0;z-index:5}}
.filters label{{font-size:14px;color:#556}}
.filters input,.filters select{{padding:9px 10px;border:1px solid #cfd6cf;border-radius:10px;font-size:15px;background:#fff}}
#cards{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:18px}}
@media(max-width:760px){{#cards{{grid-template-columns:1fr}}.hero h1{{font-size:38px}}}}
.card{{background:#fff;border:1px solid #e2e7e2;border-radius:18px;padding:18px;position:relative;box-shadow:0 4px 18px rgba(20,40,30,.05)}}
.card.followed{{border-color:#0f766e;box-shadow:0 0 0 2px #0f766e33}}
.card-top{{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;align-items:flex-start}}
.wool-score{{background:#0f766e;color:#fff;border-radius:999px;padding:3px 12px;font-weight:700;white-space:nowrap}}
.wool-score.muted{{background:#999}}
.tag{{background:#eef2f7;border-radius:999px;padding:2px 10px;font-size:13px}}
.muted{{color:#667}}
.quota{{font-size:1.15em;font-weight:700}}
.claim{{display:inline-block;background:#0f766e;color:#fff;padding:9px 15px;border-radius:10px;text-decoration:none;font-weight:700}}
.claim.muted{{background:#eee;color:#333}}
.btn{{border:1px solid #cfd6cf;background:#fff;border-radius:10px;padding:8px 12px;cursor:pointer;font-size:14px;margin-right:8px}}
.btn.on{{background:#0f766e;color:#fff;border-color:#0f766e}}
details{{margin:10px 0}}
details summary{{cursor:pointer;font-weight:600}}
section.panel{{background:#fff;border:1px solid #e2e7e2;border-radius:18px;padding:20px;margin-top:22px}}
section.panel h2{{margin-top:0}}
</style></head><body><div class="wrap">
<div class="hero">
<span class="pill">● 监控运行中 · 每日 3 档</span>
<span class="pill">在追踪 <b>{len(offers)} 条</b>（国内 {n_dom} · 海外 {n_over}）</span>
<span class="pill">范围 国内 + 海外大厂 · 文本 / 生图 / 生视频</span>
<h1>AI 羊毛<em>监控雷达</em></h1>
<p>这一版把范围扩到全球：国内大厂的一次性发放照旧追，海外大厂（Cloudflare、Agnes、Google、Groq…）本身就免费的常驻档单独立账，每日签到型、生图与生视频方案全部纳入同一套到期监控。本轮再收紧三条口径：<b>要绑卡、验证支付方式或先充值才能用的，不再计入主列表</b>；每张卡都能点开看<b>具体免费模型名单</b>；评分分两层——卡片右上角是<b>整个羊毛的易薅·实用综合分</b>（只看易薅程度和实用性，不含智力/额度），点开明细才看每个具体模型的智力 / 额度 / 实用性分，有官方领取地址的直接放跳转按钮。</p>
</div>
<div class="conclusion"><h2><span>本轮结论</span></h2>
<p><b>最近到期的固定活动在下方到期监控台按时间排好了</b>，临期 48 小时内会单独提醒；常驻与每日/每月重置档不重复打扰，只在规则变化时再报。数据来源：<code>data/offers.json</code>（单一事实源），额度/截止日只写已核实内容，未核实标注“待核实”，不编造。</p></div>
<div class="filters">
<label>搜索 <input id="q" placeholder="搜厂商 / 活动 / 模型"></label>
<label>地区 <select id="region"><option value="">全部</option><option value="domestic">国内大厂</option><option value="overseas">海外大厂</option></select></label>
<label>类型 <select id="cat"><option value="">全部</option><option value="text">文本</option><option value="image">生图</option><option value="video">生视频</option></select></label>
<label>领取方式 <select id="kind"><option value="">全部</option><option value="one_time">一次性领取</option><option value="permanent">本身就免费</option><option value="daily">每日签到</option><option value="monthly">每月重置</option></select></label>
<label>排序 <select id="sort"><option value="total">羊毛总分优先</option><option value="deadline">截止日优先</option><option value="name">名称</option></select></label>
</div>
<section id="cards">{cards}</section>
<section class="panel"><h2>自动上架（未人工核实，仅供参考）</h2><p class="muted">容易确定的线索由服务自动列在这里；分数旁标注了 heuristic（启发式）或 ai:模型名。它们仍不是已核实活动，人工核对官方原文后才进主卡片。</p><ul>{auto_html}</ul></section>
<section class="panel"><h2>自动发现 · 待核实（不是已核实活动）</h2><p class="muted">以下线索由服务自动从公开来源抓取、自动打分，未经人工核对官方原文前不得当成已核实活动；分数旁标注了 heuristic（启发式）或 ai:模型名。</p><ul>{candidates_html}</ul></section>
<section class="panel"><h2>到期监控台</h2>
<h3>固定截止日</h3><ul>{desk_fixed}</ul>
<h3>每日重置</h3><ul>{desk_daily}</ul>
<h3>每月重置</h3><ul>{desk_monthly}</ul>
<h3>无固定截止日（规则变化才报）</h3><ul>{desk_open}</ul></section>
<section class="panel"><h2>模型评分榜（只排具体模型）</h2><ol>{board}</ol></section>
<section class="panel"><h2>争议与已排除</h2><ul>{disputed}</ul><h3>已剔除（绑卡/改口径/退役）</h3><ul>{excluded}</ul></section>
<section class="panel"><h2>雷达源与检查方法</h2><ul>{sources_html}</ul>
<p>每轮先看限时清单再看常态清单，只看大陆大厂与本页在册海外大厂；每条数字必须能在官方原文里找到才算核实，聚合页收录更新不等于规则变化；抓不到正文的 JS 渲染官方页标“待人工复核”，不等于无活动；不收共享 key 池 / 逆向代理站。</p>
<p class="muted">评分公式：模型分 = 智力/额度/实用性各 1-5 分；羊毛总分 = 易薅 45% + 最值得用模型实用性 55%
（无具名模型时用活动实用性），即 易薅×20×0.45 + 实用×20×0.55。纳入标准：免费额度本身要求绑卡/绑支付方式/预充值的，不纳入。</p></section>
</div>
<script>
function tick(){{
  document.querySelectorAll('[data-expiry]').forEach(function(el){{
    var t = new Date(el.getAttribute('data-deadline')).getTime() - Date.now();
    var span = el.querySelector('.countdown');
    if (!span) return;
    if (t <= 0) {{ span.textContent = '已到期（以官方页为准）'; return; }}
    var s = Math.floor(t/1000), d = Math.floor(s/86400), h = Math.floor(s%86400/3600),
        m = Math.floor(s%3600/60), sec = s%60;
    // 单一时间戳派生：天数与时分秒来自同一个剩余秒数，不存在两种取整。
    span.textContent = '还剩 ' + d + ' 天 ' + h + ' 小时 ' + m + ' 分 ' + sec + ' 秒';
  }});
}}
setInterval(tick, 1000); tick();
var q=document.getElementById('q'), region=document.getElementById('region'),
    cat=document.getElementById('cat'), kind=document.getElementById('kind'),
    sort=document.getElementById('sort'),
    wrap=document.getElementById('cards');
function apply(){{
  var cards=[].slice.call(wrap.querySelectorAll('.card'));
  cards.forEach(function(c){{
    var ok = (!q.value || c.textContent.toLowerCase().indexOf(q.value.toLowerCase()) >= 0)
      && (!region.value || c.dataset.region === region.value)
      && (!cat.value || c.dataset.category === cat.value)
      && (!kind.value || c.dataset.kind === kind.value);
    c.style.display = ok ? '' : 'none';
  }});
  var vis = cards.filter(function(c){{ return c.style.display !== 'none'; }});
  vis.sort(function(a,b){{
    if (sort.value === 'name') return a.dataset.name.localeCompare(b.dataset.name);
    if (sort.value === 'deadline') return a.dataset.deadline.localeCompare(b.dataset.deadline);
    return (parseInt(b.dataset.total,10) - parseInt(a.dataset.total,10));
  }});
  vis.forEach(function(c){{ wrap.appendChild(c); }});
}}
[q,region,cat,kind,sort].forEach(function(el){{ el.addEventListener('input', apply); el.addEventListener('change', apply); }});
var followed = {{}};
try {{ followed = JSON.parse(localStorage.getItem('wool-followed') || '{{}}'); }} catch(e) {{}}
document.querySelectorAll('.follow-btn').forEach(function(btn){{
  var id = btn.dataset.id;
  if (followed[id]) {{ btn.classList.add('on'); btn.textContent = '已关注'; btn.closest('.card').classList.add('followed'); }}
  btn.addEventListener('click', function(){{
    if (followed[id]) {{ delete followed[id]; btn.classList.remove('on'); btn.textContent = '关注到期'; btn.closest('.card').classList.remove('followed'); }}
    else {{ followed[id] = 1; btn.classList.add('on'); btn.textContent = '已关注'; btn.closest('.card').classList.add('followed'); }}
    try {{ localStorage.setItem('wool-followed', JSON.stringify(followed)); }} catch(e) {{}}
  }});
}});
document.querySelectorAll('.copy-btn').forEach(function(btn){{
  btn.addEventListener('click', function(){{
    var txt = btn.dataset.steps;
    if (navigator.clipboard) {{ navigator.clipboard.writeText(txt).then(function(){{ btn.textContent = '已复制'; }}); }}
    else {{ var ta = document.createElement('textarea'); ta.value = txt; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); btn.textContent = '已复制'; }}
  }});
}});
</script></body></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    for name in ("icon.svg", "icon-128.png"):
        src = ASSETS / name
        if src.exists():
            (out.parent / name).write_bytes(src.read_bytes())
    print(f"wrote {out} ({len(offers)} offers)")


if __name__ == "__main__":
    main()
