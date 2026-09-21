# -*- coding: utf-8 -*-
"""Stage 7 - prove that every translated paragraph reached the PDF.

Word counts and file sizes do not prove anything: a paragraph can be silently
swallowed by a marker whose text the renderer discards, or by a CSS rule. This
walks the final PDF, concatenates the text of each unit's pages, and checks that
the first ~14 characters of every paragraph in every ``zh/<unit>.md`` appear
there. A paragraph that spans a page break may fail; two or three of those is
normal, dozens means content is missing.

Usage:  python verify_pdf.py [book.json]
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf

PROBE = 14


def main():
    cfg = common.load_config(common.config_arg(sys.argv))
    bd = cfg["build_dir"]
    folios = json.load(io.open(os.path.join(bd, "_toc_pages.json"), encoding="utf-8"))
    pdf = os.path.join(cfg["out_dir"], cfg["pdf_name"])
    first = int(cfg.get("folio_from", 2))

    doc = pymupdf.open(pdf)
    pages = ["".join(p.get_text().split()) for p in doc]
    doc.close()

    starts = sorted(((f, a) for a, f in folios.items()))
    rows = []
    checked = missing = 0
    for idx, (folio, anchor) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else 10 ** 6
        start_idx = folio + first - 1
        end_idx = end + first - 1
        body = "".join(pages[start_idx:end_idx])
        unit = None
        for u in common.units(cfg):
            if (u.get("anchor") or u["file"]) == anchor:
                unit = u
                break
        if unit is None:
            continue
        zp = common.unit_path(cfg, unit["file"], "zh")
        if not os.path.exists(zp):
            continue
        local = 0
        for line in common.read_lines(zp):
            tag, val = common.parse_marker(line)
            if tag in ("BREAK", "FIG", "CHAPNUM", "BOXIMG", "CAP"):
                continue
            if re.match(r"\*\d+\s", val):            # footnote lines
                continue
            probe = re.sub(r"[\s*]", "", val)[:PROBE]
            if not probe:
                continue
            checked += 1
            if probe not in body:
                missing += 1
                local += 1
                rows.append("MISS %-16s folio %-4d %s" % (anchor, folio, val[:64]))
        rows.append("  %-16s folio %-4d paragraphs ok%s"
                    % (anchor, folio, "" if not local else "  (%d missing)" % local))

    head = ["checked paragraphs = %d" % checked,
            "missing = %d  (%.2f%%)" % (missing, 100.0 * missing / max(checked, 1)),
            "a handful of misses usually means a paragraph straddling a page "
            "break; investigate anything beyond that", ""]
    common.log_to(cfg, "_verify.txt", head + rows)
    print("\n".join(head))
    print("\n".join(r for r in rows if r.startswith("MISS"))[:3000])


if __name__ == "__main__":
    main()
