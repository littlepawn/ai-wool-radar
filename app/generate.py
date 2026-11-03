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


def render_card(o):
    total = o["wool_total"]
    badge = f'<span class="wool-score" title="易薅 45% + 实用 55%">易薅·实用 {total}</span>' \
        if total is not None else '<span class="wool-score muted">未评分</span>'
    deadline_attr = f' data-deadline="{escape(o["deadline"])}"' if o.get("deadline") else ""
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
    ver = escape(o.get("verification") or "")
    return f"""
<article class="card" data-region="{o["region"]}" data-category="{o["category"]}"
  data-kind="{o["kind"]}" data-total="{total if total is not None else -1}"
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
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 羊毛监控雷达（独立版）</title>
<style>
body{{font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;max-width:1080px;margin:0 auto;padding:16px;line-height:1.6}}
.card{{border:1px solid #ddd;border-radius:12px;padding:16px;margin:16px 0;position:relative}}
.card-top{{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}}
.wool-score{{background:#0f766e;color:#fff;border-radius:999px;padding:2px 12px;font-weight:700}}
.wool-score.muted{{background:#999}}
.tag{{background:#eef2f7;border-radius:999px;padding:2px 10px}}
.muted{{color:#666}} .quota{{font-size:1.15em;font-weight:700}}
.claim{{display:inline-block;background:#0f766e;color:#fff;padding:8px 14px;border-radius:8px;text-decoration:none}}
.claim.muted{{background:#eee;color:#333}}
input,select{{padding:8px;margin:4px}}
</style></head><body>
<h1>AI 羊毛监控雷达（独立版）</h1>
<p>数据来源：<code>data/offers.json</code>（单一事实源）。额度/截止日只写已核实内容，未核实标注“待核实”，不编造。
模型分与羊毛总分为编辑评分，非官方数据。纳入标准：免费额度本身要求绑卡/绑支付方式/预充值的，不纳入。</p>
<p><label>搜索 <input id="q" placeholder="搜厂商 / 活动 / 模型"></label>
<label>地区 <select id="region"><option value="">全部</option><option value="domestic">国内大厂</option><option value="overseas">海外大厂</option></select></label>
<label>类型 <select id="cat"><option value="">全部</option><option value="text">文本</option><option value="image">生图</option><option value="video">生视频</option></select></label>
<label>排序 <select id="sort"><option value="total">羊毛总分优先</option><option value="name">名称</option></select></label></p>
<section id="cards">{cards}</section>
<h2>模型评分榜（只排具体模型）</h2><ol>{board}</ol>
<h2>争议与已排除</h2><ul>{disputed}</ul><h3>已剔除（绑卡/改口径/退役）</h3><ul>{excluded}</ul>
<p class="muted">评分公式：模型分 = 智力/额度/实用性各 1-5 分；羊毛总分 = 易薅 45% + 最值得用模型实用性 55%
（无具名模型时用活动实用性），即 易薅×20×0.45 + 实用×20×0.55。</p>
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
    cat=document.getElementById('cat'), sort=document.getElementById('sort'),
    wrap=document.getElementById('cards');
function apply(){{
  var cards=[].slice.call(wrap.querySelectorAll('.card'));
  cards.forEach(function(c){{
    var ok = (!q.value || c.textContent.toLowerCase().indexOf(q.value.toLowerCase()) >= 0)
      && (!region.value || c.dataset.region === region.value)
      && (!cat.value || c.dataset.category === cat.value);
    c.style.display = ok ? '' : 'none';
  }});
  var vis = cards.filter(function(c){{ return c.style.display !== 'none'; }});
  vis.sort(function(a,b){{
    return sort.value === 'name' ? a.dataset.name.localeCompare(b.dataset.name)
      : (parseInt(b.dataset.total,10) - parseInt(a.dataset.total,10));
  }});
  vis.forEach(function(c){{ wrap.appendChild(c); }});
}}
[q,region,cat,sort].forEach(function(el){{ el.addEventListener('input', apply); el.addEventListener('change', apply); }});
</script></body></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({len(offers)} offers)")


if __name__ == "__main__":
    main()
