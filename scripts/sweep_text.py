# -*- coding: utf-8 -*-
"""Stage 4 - copy-editing sweep over the translated marker files.

Scans for the defects that survive a line-by-line translation pass:

  * ASCII quote characters embedded in Chinese text
  * a line that BEGINS with a closing quote -> the closing quote of the previous
    line was pushed across a line break, and will render as a stray character
  * doubled punctuation (，，。。、，)
  * doubled function words that cannot occur in correct Chinese (和和 了了 就就)
  * half-width , ; : ! ? between two CJK characters
  * unbalanced full-width parentheses
  * chapter guide length out of the configured range

Usage:  python sweep_text.py [book.json]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

CJK = r"\u4e00-\u9fa5"
# Only pairs that cannot occur in correct Chinese prose. Measure words are
# deliberately absent: 一把把 / 一个个 / 一条条 are valid reduplication, and
# 可以以… / 有目的的 are legitimate boundaries that a naive repeat-check flags.
BAD_DOUBLES = [
    "和和", "了了", "就就", "在在", "是是", "我我", "你你", "他他", "她她",
    "它它", "也也", "都都", "与与", "及及", "被被", "对对", "而而", "则则",
    "让让", "给给", "从从", "向向", "跟跟", "很很", "太太", "更更", "最最",
    "还还", "又又", "再再", "没没", "不不", "无无", "们们", "这这", "那那",
    "有有", "使使", "的的",
]
# 的的 is correct after a noun ending in 的 (有目的的 / 无目的的).
DUP_OK = re.compile(r"(目的|的)的的")

CHECKS = [
    ("ASCII 单引号", re.compile(r"[" + CJK + r"]'|'[" + CJK + r"]")),
    ("ASCII 双引号", re.compile(r'[' + CJK + r']"|"[' + CJK + r']')),
    ("重复标点", re.compile(r"[，。、；：]{2,}")),
    ("半角标点", re.compile(r"[" + CJK + r"][,;:!?][" + CJK + r"]")),
    ("多余空格", re.compile(r"[" + CJK + r"] {2,}[" + CJK + r"]")),
]


def sweep_unit(cfg, unit):
    path = common.unit_path(cfg, unit["file"], "zh")
    if not os.path.exists(path):
        return [], []
    issues, guides = [], []
    for i, l in enumerate(common.read_lines(path), 1):
        tag, val = common.parse_marker(l)
        body = val.strip()
        if not body:
            continue
        if tag == "GUIDE":
            guides.append(body)
        if body.startswith(("”", "’", "」")):
            issues.append(("行首孤立闭引号", i, body[:58]))
        for label, pat in CHECKS:
            if pat.search(body):
                issues.append((label, i, body[:58]))
                break
        for pair in BAD_DOUBLES:
            k = body.find(pair)
            if k < 0:
                continue
            if pair == "的的" and DUP_OK.search(body):
                continue
            issues.append(("叠字 " + pair, i, body[max(0, k - 16):k + 18]))
            break
        if body.count("（") != body.count("）"):
            issues.append(("括号不配对", i, body[:58]))
    return issues, guides


def main():
    cfg = common.load_config(common.config_arg(sys.argv))
    g = cfg.get("guide") or {}
    lo, hi = g.get("min_chars", 240), g.get("max_chars", 360)
    rows = []
    total = 0
    for unit in common.units(cfg):
        issues, guides = sweep_unit(cfg, unit)
        name = unit["file"]
        if guides:
            chars = sum(len(x) for x in guides)
            note = ""
            if not (g.get("min_paras", 2) <= len(guides) <= g.get("max_paras", 3)):
                note = "  <== paragraph count"
            if not (lo <= chars <= hi):
                note = "  <== length"
            rows.append("GUIDE  %-26s paras=%d chars=%d%s"
                        % (name, len(guides), chars, note))
        for label, i, frag in issues:
            total += 1
            rows.append("  %-18s %-26s L%-5d %s" % (label, name, i, frag))
    rows.insert(0, "issues found: %d" % total)
    rows.insert(1, "")
    path = common.log_to(cfg, "_sweep.txt", rows)
    print("\n".join(rows[:60]))
    print("\nwritten:", path)


if __name__ == "__main__":
    main()
