"""自动上架：把“容易确定”的线索自动列入页面主列表旁的自动上架区，
“很难确定”的线索继续留在待核实区，等人工介入。

自动上架的判定（必须全部满足，缺一不可）：
  1. 已评分，且 needs_card_binding=false（绑卡的按口径不进主列表）；
  2. 有明确额度信号：文本含数字 + token/积分/credits/次/万/亿其一；
  3. 易薅分 >= 3（领取路径不含审核、提交作品、排队等高摩擦词）；
  4. 不是纯工具类线索：线索开头标为“工具”类（IDE / App 等）的，
     模型归属说不清，一律留待人工，不自动上架；
  5. 置信度不能是 low（启发式无量级、AI 低置信都算难确定）。

不满足任一条 → status 保持 needs_review，页面上只出现在待核实区。
自动上架 ≠ 已核实：上架区卡片带“自动上架 · 未人工核实”标记，
分数旁标注 heuristic 或 ai:<模型名>，且不进入主卡片的模型评分榜；
只有人工核对官方原文后，才可手工进入 data/offers.json 的已核实列表。

用法：python3 app/promote.py [--candidates state/candidates.json]
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUOTA_SIGNAL = re.compile(r"\d+\s*(?:tokens?|Token|积分|credits|次|万|亿)")


def is_clear(c):
    sc = c.get("score") or {}
    if sc.get("needs_card_binding"):
        return False, "needs_card_binding"
    if (sc.get("confidence") or "low") == "low":
        return False, "low_confidence"
    if (sc.get("ease") or 0) < 3:
        return False, "low_ease"
    snippet = c.get("snippet", "")
    if snippet.startswith("点击领取 → 工具") or " → 工具 " in snippet[:30]:
        return False, "tool_only"
    if not QUOTA_SIGNAL.search(snippet):
        return False, "no_quota_signal"
    return True, "clear"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=str(ROOT / "state" / "candidates.json"))
    args = ap.parse_args()
    path = Path(args.candidates)
    if not path.exists():
        print("promote: no candidates file yet", flush=True)
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    n_auto = n_review = 0
    for c in data.get("candidates", []):
        if c.get("status") == "auto_listed":
            n_auto += 1
            continue
        if c.get("score") is None:
            n_review += 1
            continue
        ok, reason = is_clear(c)
        if ok:
            c["status"] = "auto_listed"
            n_auto += 1
        else:
            c["status"] = "needs_review"
            c["review_reason"] = reason
            n_review += 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"promote: auto_listed={n_auto} needs_review={n_review} -> {path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
