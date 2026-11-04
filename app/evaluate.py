"""自动评估：给自动发现的线索打分。分两档，AI 只是可选项。

1. 启发式评分（默认，永远可用，不花钱）：
   从线索文本里解析额度量级、模型档位词、领取摩擦词，给出
   智力 / 额度 / 实用性 / 易薅 各 1-5 分，score_source="heuristic"。
2. AI 评分（可选，需配置才启用）：
   环境变量 AI_API_KEY + AI_MODEL 都设置后，才会调用
   AI_BASE_URL（默认 https://api.openai.com/v1）上 OpenAI 兼容的
   /chat/completions 接口。没有 Key 就静默跳过 AI，只用启发式，
   绝不因缺 Key 而报错中断服务。Key 只从环境变量读，绝不打印、
   不写进任何文件。

AI 提示词（本文件作者设定，见 AI_SYSTEM_PROMPT / AI_USER_TEMPLATE）：
- 只根据提供的线索文本打分，不许编造额度、截止日、模型名；
- 证据不足时置信度写 low、对应分数写 null，不许猜一个漂亮数字；
- 免费本身要求绑卡 / 绑支付方式 / 预充值时，needs_card_binding=true，
  这类线索按项目口径不进主列表；
- 只输出严格 JSON，不输出多余文字。

用法：
    python3 app/evaluate.py [--candidates state/candidates.json]
    # 默认就地更新同一文件，给每条未评分线索补 score / score_source。
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

AI_SYSTEM_PROMPT = (
    "你是一个严谨的免费 AI 额度评估员。只根据用户提供的线索文本评估，"
    "绝不编造任何额度、截止日、模型名或领取步骤。\n"
    "输出严格 JSON，不要输出任何多余文字，格式如下：\n"
    '{"intelligence": 1-5或null, "quota": 1-5或null, '
    '"practicality": 1-5或null, "ease": 1-5或null, '
    '"confidence": "high"|"medium"|"low", '
    '"needs_card_binding": true|false, '
    '"reason": "一句话中文理由，如实说明依据或证据不足之处"}\n'
    "评分口径：intelligence 看模型档位（旗舰/Pro/Max 高，Flash/Mini/Lite 低）；"
    "quota 看额度量级（越大越高，无法换算成 token 量时写 null）；"
    "practicality 看额度好不好用、有无水印或商用限制；"
    "ease 看领取摩擦（注册即用高，需审核、提交作品、邀请排队低）。"
    "证据不足时对应分数写 null、confidence 写 low，宁可空着也不猜。"
)

AI_USER_TEMPLATE = (
    "线索来源：{source_name}（{url}）\n"
    "线索文本：{snippet}\n"
    "请按系统提示词输出严格 JSON。"
)

FLAGSHIP = ("pro", "max", "ultra", "opus", "旗舰", "最强", "GPT-5", "Claude Opus", "GLM-4.6", "Qwen3-Max")
LIGHT = ("flash", "mini", "lite", "nano", "Flash", "Mini", "轻量")


def parse_tokens(text):
    """把“5亿/1亿/100万 tokens”这类量级换算成约 token 数，换算不出返回 None。"""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(亿|万)\s*(?:tokens?|Token|额度|积分)?", text)
    if m:
        v = float(m.group(1))
        return int(v * (10 ** 8 if m.group(2) == "亿" else 10 ** 4))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:million|M)\s*tokens?", text, re.I)
    if m:
        return int(float(m.group(1)) * 10 ** 6)
    return None


def heuristic(snippet):
    tokens = parse_tokens(snippet)
    if tokens is None:
        quota = 3
    elif tokens >= 10 ** 8:
        quota = 5
    elif tokens >= 10 ** 7:
        quota = 4
    elif tokens >= 10 ** 6:
        quota = 3
    else:
        quota = 2
    low = snippet.lower()
    intelligence = 5 if any(k.lower() in low for k in FLAGSHIP) else (
        2 if any(k.lower() in low for k in LIGHT) else 3)
    ease = 2 if any(w in snippet for w in ("审核", "提交作品", "排队", "邀请")) else (
        4 if "签到" in snippet or "每日" in snippet else 5)
    practicality = 3
    if "水印" in snippet:
        practicality = 2
    needs_card = any(w in snippet for w in ("绑卡", "绑定支付", "预充值", "验证支付方式"))
    return {
        "intelligence": intelligence, "quota": quota,
        "practicality": practicality, "ease": ease,
        "confidence": "medium" if tokens is not None else "low",
        "needs_card_binding": needs_card,
        "reason": "启发式评分：量级与档位词推断，未经官方原文核实",
    }


def ai_evaluate(snippet, source_name, url):
    key = os.environ.get("AI_API_KEY", "").strip()
    model = os.environ.get("AI_MODEL", "").strip()
    if not key or not model:
        return None, "disabled"
    base = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    body = json.dumps({
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            {"role": "user", "content": AI_USER_TEMPLATE.format(
                source_name=source_name, url=url, snippet=snippet)},
        ],
    }, ensure_ascii=False).encode()
    req = urllib.request.Request(
        f"{base}/chat/completions", data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        text = data["choices"][0]["message"]["content"].strip()
        # 容忍模型在 JSON 外包一层 ```json 围栏。
        text = re.sub(r"^```(?:json)?|```$", "", text.strip())
        score = json.loads(text)
        for k in ("intelligence", "quota", "practicality", "ease"):
            if score.get(k) is not None:
                score[k] = max(1, min(5, int(score[k])))
        return score, "ai"
    except Exception as e:
        return None, f"ai_failed:{type(e).__name__}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=str(ROOT / "state" / "candidates.json"))
    args = ap.parse_args()
    path = Path(args.candidates)
    if not path.exists():
        print("evaluate: no candidates file yet, run app/discover.py first", flush=True)
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    n_ai = n_heur = 0
    for c in data.get("candidates", []):
        if c.get("score") is not None:
            continue
        score, status = ai_evaluate(c["snippet"], c.get("source_name", ""), c.get("url", ""))
        if score is not None:
            c["score"] = score
            c["score_source"] = f"ai:{os.environ.get('AI_MODEL', '')}"
            n_ai += 1
        else:
            c["score"] = heuristic(c["snippet"])
            c["score_source"] = "heuristic" + ("" if status == "disabled" else f" (ai {status})")
            n_heur += 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"evaluate: ai={n_ai} heuristic={n_heur} -> {path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
