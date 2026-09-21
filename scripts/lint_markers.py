# -*- coding: utf-8 -*-
"""Stage 3b - structural lint for the translated marker files.

Catches the failure modes that silently destroy content or wreck the layout:

  * prose absorbed into a marker whose text the renderer discards
    (%%CHAPNUM%% %%BREAK%% %%FIG%% %%ENDBOX%% %%ENDEX%%) -> the prose is LOST
  * unbalanced box / exercise blocks
  * a %%FIG%% line whose "filename" is not a filename
  * %%CAP%% not attached to a figure
  * a chapter unit with no %%CT%% title
  * chapter guide (%%GUIDE%%) paragraph count and length out of range

Usage:  python lint_markers.py [book.json]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

DROPPED = {"CHAPNUM", "BREAK", "ENDBOX", "ENDEX"}
# Markers that carry a value the renderer consumes as a path, not as prose.
PATHLIKE = {"FIG", "BOXIMG"}
FILENAME_OK = re.compile(r"^[\w\-. ()]+\.(jpg|jpeg|png|gif|svg|webp)$", re.I)
SENTENCE_END = "。！？；”』"


def lint_unit(cfg, unit, issues):
    name = unit["file"]
    path = common.unit_path(cfg, name, "zh")
    if not os.path.exists(path):
        issues.append("MISSING  %s" % name)
        return None
    lines = common.read_lines(path)
    open_box = open_ex = 0
    guides = []
    has_ct = False
    for i, l in enumerate(lines, 1):
        tag, val = common.parse_marker(l)
        body = val.strip()
        if tag == "CT":
            has_ct = True
        if tag in PATHLIKE:
            if not FILENAME_OK.match(body):
                issues.append("%s L%d %%%s%% value is not a filename: %s"
                              % (name, i, tag, body[:44]))
            elif common.cjk_count(body):
                issues.append("%s L%d %%%s%% value contains CJK" % (name, i, tag))
        if tag in ("BOXT", "EXT"):
            if tag == "BOXT":
                open_box += 1
            else:
                open_ex += 1
        if tag in ("ENDBOX", "ENDEX"):
            if tag == "ENDBOX":
                open_box -= 1
            else:
                open_ex -= 1
            if open_box < 0 or open_ex < 0:
                issues.append("%s L%d unbalanced %%%s%%" % (name, i, tag))
                open_box = max(open_box, 0)
                open_ex = max(open_ex, 0)
        if tag == "CAP":
            # Publishers differ: the caption may sit above the image or below it.
            neigh = [common.parse_marker(lines[j])[0]
                     for j in (i - 2, i) if 0 <= j < len(lines)]
            if "FIG" not in neigh:
                issues.append("%s L%d CAP is not adjacent to a FIG (neighbours=%s)"
                              % (name, i, ",".join(neigh)))
        if tag in DROPPED:
            # a dropped-marker line that carries prose means lost content
            if len(body) > 24 or any(ch in body for ch in SENTENCE_END):
                issues.append("%s L%d %%%s%% absorbs prose -> CONTENT LOSS: %s"
                              % (name, i, tag, body[:52]))
        if tag == "GUIDE":
            guides.append(body)
    if open_box:
        issues.append("%s unbalanced BOXT/ENDBOX (net %+d)" % (name, open_box))
    if open_ex:
        issues.append("%s unbalanced EXT/ENDEX (net %+d)" % (name, open_ex))
    if not unit.get("front") and not has_ct:
        issues.append("%s has no %%%%CT%%%% chapter title" % name)
    if guides:
        chars = sum(len(g) for g in guides)
        if not (2 <= len(guides) <= 3):
            issues.append("%s guide has %d paragraphs (want 2-3)" % (name, len(guides)))
        if not (240 <= chars <= 360):
            issues.append("%s guide is %d chars (want 240-360)" % (name, chars))
    return len(guides)


def main():
    cfg = common.load_config(common.config_arg(sys.argv))
    issues = []
    guides = 0
    total = 0
    for unit in common.units(cfg):
        total += 1
        g = lint_unit(cfg, unit, issues)
        guides += 1 if g else 0
    rows = ["units=%d  with guide=%d" % (total, guides), ""]
    if issues:
        rows += issues
    else:
        rows.append("no structural problems found")
    path = common.log_to(cfg, "_lint.txt", rows)
    print("\n".join(rows))
    print("\nwritten:", path)


if __name__ == "__main__":
    main()
