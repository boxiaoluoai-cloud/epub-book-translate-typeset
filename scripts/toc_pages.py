# -*- coding: utf-8 -*-
"""Stage 6b - find the folio of every unit's opening page.

The TOC of a printed book needs real page numbers, but the page numbers do not
exist until the PDF is rendered. So: render once with an empty TOC, locate where
each unit starts, write the folios to _toc_pages.json, then re-run build_html.py
and html_to_pdf.py. Re-running this script a second time should produce an
identical file -- that is the convergence test (`STABLE`).

Usage:  python toc_pages.py [book.json]
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

try:
    import pymupdf
except ImportError:                                   # older wheels
    import fitz as pymupdf


def page_texts(pdf):
    doc = pymupdf.open(pdf)
    out = ["".join(p.get_text().split()) for p in doc]
    doc.close()
    return out


def body_start(pages, toc_title):
    """Index of the first page after the table of contents."""
    key = "".join((toc_title or "目录").split())
    end = 0
    for i in range(min(8, len(pages))):
        if key in pages[i]:
            end = i + 1
    return end


def expectation(cfg):
    """Ordered list of (anchor, needle) in the order they must appear."""
    pmap = common.part_map(cfg)
    order = []
    seen_parts = set()
    for unit in common.units(cfg):
        pid = unit.get("part")
        if pid and pid not in seen_parts:
            seen_parts.add(pid)
            part = pmap.get(pid) or {}
            order.append((pid, "".join((part.get("num", "")
                                        + part.get("title", "")).split())))
        anchor = unit.get("anchor") or unit["file"]
        lines = []
        zp = common.unit_path(cfg, unit["file"], "zh")
        if os.path.exists(zp):
            lines = common.read_lines(zp)
        if unit.get("front"):
            label = unit.get("label")
            if not label:
                for l in lines:
                    tag, val = common.parse_marker(l)
                    if tag == "H3":
                        label = val
                        break
            order.append((anchor, "".join((label or "").split())))
        else:
            num = common.chapter_number(unit) or ""
            title = ""
            for l in lines:
                tag, val = common.parse_marker(l)
                if tag == "CT":
                    title = val
                    break
            order.append((anchor, "".join((num + title).split())))
    return order


def main():
    cfg = common.load_config(common.config_arg(sys.argv))
    raw = os.path.join(cfg["out_dir"], cfg.get("raw_pdf", "_raw.pdf"))
    pages = page_texts(raw)
    n = len(pages)
    start = body_start(pages, cfg.get("toc_title"))
    order = expectation(cfg)

    log = ["pdf=%s pages=%d body_starts_at_index=%d" % (raw, n, start)]
    result = {}
    ptr = start
    ok = True
    for anchor, needle in order:
        found = None
        if needle:
            for i in range(ptr, n):
                if pages[i].startswith(needle):
                    found = i
                    break
        if found is None:
            ok = False
            log.append("MISS     %-16s needle=%s" % (anchor, needle))
            continue
        ptr = found + 1
        folio = found - start + 1
        result[anchor] = folio
        log.append("%-16s folio=%-4d head=%s" % (anchor, folio, pages[found][:34]))

    converged = "n/a"
    out = os.path.join(cfg["build_dir"], "_toc_pages.json")
    if ok and len(result) == len(order):
        prev = None
        if os.path.exists(out):
            prev = json.load(io.open(out, encoding="utf-8"))
        common.write_json(out, result)
        converged = "STABLE" if prev == result else "CHANGED"
        log.append("written=%s  convergence=%s" % (out, converged))
        log.append("Re-run build_html.py + html_to_pdf.py, then run this again; "
                   "when it reports STABLE the TOC is settled.")
    log.append("order_ok=%s  count=%d/%d" % (ok, len(result), len(order)))
    common.log_to(cfg, "_tocpages.txt", log)
    print("\n".join(log))


if __name__ == "__main__":
    main()
