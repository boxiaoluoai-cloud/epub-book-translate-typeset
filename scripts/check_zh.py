# -*- coding: utf-8 -*-
"""Stage 3 - translation self-check: completeness and structural fidelity.

Reports, per unit:
  * EN lines / ZH lines and whether the marker sequences line up one-to-one
  * total CJK characters vs total English words (expect roughly 1.5-2.0)
  * prose lines that contain no CJK at all      -> likely untranslated
  * prose lines that still carry Latin words    -> leakage to clean up
  * lines that are empty after their marker     -> content dropped by a rewrite

Usage:  python check_zh.py [book.json]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

# markers whose value is layout-only, so an empty value is fine
LAYOUT_ONLY = {"BREAK", "FIG", "CHAPNUM", "BOXIMG", "VERSE"}
# markers whose text is discarded by the renderer: prose absorbed here is LOST
DROPPED = {"CHAPNUM", "BREAK", "FIG", "ENDBOX", "ENDEX", "BOXIMG"}
# Latin words tolerated in Chinese prose. Deliberately minimal: only acronyms
# and symbols that Chinese readers routinely meet untranslated. Anything a
# particular book keeps on purpose (a coined term, a house acronym, an
# untranslated slogan) belongs in that book's `latin_allow` list in book.json --
# never here. Keeping this list short is what makes the check portable.
ALLOW = {
    "AI", "IQ", "EQ", "MBA", "MFA", "PhD", "MD", "BA", "GPS", "USB", "LED",
    "Wi-Fi", "Wifi", "PDF", "HTML", "URL", "DNA", "RNA", "CEO", "CFO", "CTO",
    "CT", "MRI", "NASA", "ISBN", "RGB", "TV", "OK",
    "AND", "OR", "NOT", "A", "B",
}
ALLOW_LOWER = {w.lower() for w in ALLOW}
PARENS = re.compile(r"（[^（）]*）|\([^()]*\)|【[^【】]*】|\[[^\[\]]*\]")


def main():
    cfg = common.load_config(common.config_arg(sys.argv))
    # A book may legitimately keep certain Latin words inline (a coined term, a
    # symbol, an acronym the author uses untranslated). Extend the list per book
    # rather than loosening the check for everyone.
    allow = set(ALLOW_LOWER)
    allow |= {w.lower() for w in (cfg.get("latin_allow") or [])}
    allow |= {w for w in (cfg.get("latin_allow") or [])}
    rows = []
    problems = 0
    for unit in common.units(cfg):
        name = unit["file"]
        ep, zp = common.unit_path(cfg, name, "src"), common.unit_path(cfg, name, "zh")
        if not os.path.exists(zp):
            rows.append("MISSING  %-26s (no translation yet)" % name)
            problems += 1
            continue
        e_lines = common.read_lines(ep) if os.path.exists(ep) else []
        z_lines = common.read_lines(zp)
        e_tags = [common.parse_marker(l)[0] for l in e_lines]
        # The ZH file may legitimately carry extra GUIDE paragraphs (chapter
        # reading guides) and extra CAP lines (captions written for figures that
        # had none upstream). Treat both as insertions so they do not consume an
        # English line -- otherwise every following line mis-pairs.
        z_tags, ei, inserted = [], 0, 0
        for l in z_lines:
            t = common.parse_marker(l)[0]
            et = e_tags[ei] if ei < len(e_tags) else None
            if t == "GUIDE" or (t == "CAP" and et != "CAP"):
                inserted += 1
                continue
            z_tags.append(t)
            ei += 1

        e_w = sum(common.latin_words(common.strip_markup(l)) for l in e_lines)
        # The reading guide is an editorial addition, not a translation of the
        # source. Counting it would inflate the ratio and could mask a real
        # omission, so it is excluded here.
        z_c = sum(common.cjk_count(common.strip_markup(l)) for l in z_lines
                  if common.parse_marker(l)[0] != "GUIDE")
        ratio = z_c / float(e_w) if e_w else 0.0

        aligned = e_tags == z_tags
        flags = []
        if not aligned:
            # locate the first divergence for a usable message
            for i in range(max(len(e_tags), len(z_tags))):
                a = e_tags[i] if i < len(e_tags) else "(end)"
                b = z_tags[i] if i < len(z_tags) else "(end)"
                if a != b:
                    flags.append("marker diverge at line %d: EN=%s ZH=%s" % (i + 1, a, b))
                    break
            flags.append("EN tags=%d ZH tags=%d" % (len(e_tags), len(z_tags)))

        for i, l in enumerate(z_lines, 1):
            tag, val = common.parse_marker(l)
            body = common.strip_markup(val)
            if tag in DROPPED:
                continue
            if not body and tag not in LAYOUT_ONLY:
                flags.append("L%d empty body after %%%%%s%%%%" % (i, tag))
                continue
            if not body:
                continue
            if common.cjk_count(body) == 0 and common.latin_words(body) >= 3:
                flags.append("L%d untranslated: %s" % (i, body[:50]))
                continue
            # A parenthetical is an original-language gloss by construction, so
            # only look for leakage outside parentheses and brackets.
            loose = PARENS.sub("", body)
            for w in re.findall(r"[A-Za-z][A-Za-z'\-]{2,}", loose):
                if w.lower() in allow:
                    continue
                flags.append("L%d latin left: %s | %s" % (i, w, body[:44]))
                break

        status = "ok" if not flags else "CHECK"
        rows.append("%s  %-26s EN %5d w / ZH %6d ch  ratio %.2f  insertions %d"
                    % (status, name, e_w, z_c, ratio, inserted))
        for f in flags[:8]:
            rows.append("        " + f)
        if flags:
            problems += 1

    rows.append("")
    rows.append("units with problems: %d" % problems)
    rows.append("ratio guide: 1.5-2.0 is normal for zh-CN prose; far below "
                "means content was dropped, far above means the translator "
                "expanded the source.")
    path = common.log_to(cfg, "_check.txt", rows)
    print("\n".join(rows))
    print("\nwritten:", path)


if __name__ == "__main__":
    main()
