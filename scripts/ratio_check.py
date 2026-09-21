# -*- coding: utf-8 -*-
"""Stage 3c - per-line completeness check.

Pairs each English line with its Chinese counterpart and compares
CJK characters against English words. Lines far below the chapter's own mean
are omission candidates; lines far above are expansion candidates. Only the
outliers are printed, so the report stays readable on a 100k-character book.

The pairing is marker-aware: extra ZH lines that legitimately do not correspond
to an English line (chapter guides, captions written for figure-less images) are
treated as insertions instead of consuming an English line.

Usage:  python ratio_check.py [book.json] [--low 0.6] [--high 3.0]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

SKIP = {"BREAK", "FIG", "CHAPNUM", "GUIDE", "BOXIMG"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", nargs="?", default=None)
    ap.add_argument("--low", type=float, default=0.6,
                    help="flag lines below this fraction of the chapter mean")
    ap.add_argument("--high", type=float, default=3.0,
                    help="flag lines above this absolute ratio")
    ap.add_argument("--show", type=int, default=12)
    args = ap.parse_args()

    cfg = common.load_config(args.config)
    rows = []
    for unit in common.units(cfg):
        name = unit["file"]
        ep, zp = common.unit_path(cfg, name, "src"), common.unit_path(cfg, name, "zh")
        if not (os.path.exists(ep) and os.path.exists(zp)):
            continue
        e_lines = common.read_lines(ep)
        z_lines = common.read_lines(zp)
        pairs, ei, inserted = [], 0, 0
        for z in z_lines:
            zt = common.parse_marker(z)[0]
            et = common.parse_marker(e_lines[ei])[0] if ei < len(e_lines) else ""
            if zt == "GUIDE" or (zt == "CAP" and et != "CAP"):
                pairs.append((None, z))
                inserted += 1
                continue
            e = e_lines[ei] if ei < len(e_lines) else ""
            ei += 1
            pairs.append((e, z))

        tot_e = tot_z = 0
        cand = []
        for e, z in pairs:
            if e is None:
                continue
            etag = common.parse_marker(e)[0]
            ew = common.latin_words(common.strip_markup(e))
            zc = common.cjk_count(common.strip_markup(z))
            tot_e += ew
            tot_z += zc
            if etag in SKIP or ew < 8:
                continue
            cand.append((zc / float(ew), ew, zc, common.strip_markup(e), common.strip_markup(z)))
        mean = tot_z / float(tot_e) if tot_e else 0
        leftovers = len(e_lines) - ei
        rows.append("==== %-26s EN %5d w / ZH %6d ch  mean %.2f  |  ZH insertions %d"
                    " | EN unconsumed %d" % (name, tot_e, tot_z, mean, inserted, leftovers))
        out = sorted([c for c in cand
                      if c[0] < mean * args.low or c[0] > args.high],
                     key=lambda x: x[0])
        for r, ew, zc, e, z in out[:args.show]:
            rows.append("  r=%.2f  ew=%-4d cc=%-4d" % (r, ew, zc))
            rows.append("    EN " + e[:150])
            rows.append("    ZH " + z[:88])
        rows.append("")
    rows.append("Reading the report: a low ratio on a prose line means the "
                "Chinese says less than the English. Check those lines against "
                "the source; paragraph splits inside a long English paragraph "
                "are a common and harmless cause.")
    path = common.log_to(cfg, "_ratio.txt", rows)
    print("\n".join(rows[:40]))
    print("\nwritten:", path)


if __name__ == "__main__":
    main()
