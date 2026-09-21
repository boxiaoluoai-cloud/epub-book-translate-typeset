# -*- coding: utf-8 -*-
"""Stage 6c - stamp folios (page numbers) and running heads onto the PDF.

The numbers cannot be produced by the browser (Chromium has no CSS page
counter), so they are drawn on top with reportlab. Several details matter:

  * Draw every page onto ONE overlay document. Drawing a separate one-page
    overlay per page makes reportlab embed the CJK font once per page.
  * Subset that font first (fontTools). A full SimSun is ~17 MB; the running
    heads need a few dozen glyphs, which come to ~20 KB.
  * Build the writer with ``PdfWriter()`` + ``add_page(reader_page)`` so the
    book's own fonts stay shared. ``PdfWriter(clone_from=...)`` copies them per
    page (a 4 MB book becomes 13 MB).
  * ``merge_page`` leaves content streams uncompressed. Call
    ``compress_content_streams()`` afterwards, on pages that already belong to
    the writer (calling it on a reader page raises "Page must be part of a
    PdfWriter"). Without this the file grows ~10x.

Usage:  python stamp.py [book.json]
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

MM = 2.8346                                   # millimetres -> points
FOLIO_FROM = 2                                # 0-based index of the first body page
DEFAULT_FONTS = [
    (r"C:\Windows\Fonts\simsun.ttc", 0),
    (r"C:\Windows\Fonts\simhei.ttf", 0),
    (r"C:\Windows\Fonts\simkai.ttf", 0),
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 0),
    ("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 0),
]


def ensure_subset(cfg, chars, log):
    """Reduce the running-head font to the glyphs actually used."""
    src = cfg.get("head_font")
    if not src:
        for path, _ in DEFAULT_FONTS:
            if os.path.exists(path):
                src = path
                break
    if not src or not os.path.exists(src):
        log.append("head font: none found, running heads will be skipped")
        return None
    dst = os.path.join(cfg["build_dir"], "_head_subset.ttf")
    try:
        import logging
        logging.getLogger("fontTools.subset").setLevel(logging.ERROR)
        logging.getLogger("fontTools.ttLib").setLevel(logging.ERROR)
        from fontTools import subset
        from fontTools.ttLib import TTFont
        opts = subset.Options()
        opts.layout_features = []
        opts.drop_tables += ["DSIG"]
        opts.notdef_outline = True
        font = TTFont(src, fontNumber=0)
        s = subset.Subsetter(options=opts)
        s.populate(text="".join(sorted(chars)))
        s.subset(font)
        subset.save_font(font, dst, opts)
        log.append("head font: %s -> subset %.1f KB (%d glyphs)"
                   % (os.path.basename(src), os.path.getsize(dst) / 1024.0,
                      len(chars)))
        return dst
    except ImportError:
        log.append("head font: fontTools missing, using full font (PDF will be "
                   "much larger; pip install fonttools)")
        return src
    except Exception as e:
        log.append("head font: subsetting failed (%s), using full font" % str(e)[:80])
        return src


def head_for(folio, runs, labels, opens, book_title):
    if folio in opens:
        return None                        # unit opening page: no running head
    if folio % 2 == 0:
        return book_title
    cur = None
    for f, anchor in runs:
        if f <= folio:
            cur = anchor
        else:
            break
    return (labels.get(cur) or book_title) if cur else None


def main():
    cfg = common.load_config(common.config_arg(sys.argv))
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.colors import Color

    raw = os.path.join(cfg["out_dir"], cfg.get("raw_pdf", "_raw.pdf"))
    dst = os.path.join(cfg["out_dir"], cfg["pdf_name"])
    bd = cfg["build_dir"]
    labels = json.load(io.open(os.path.join(bd, "_labels.json"), encoding="utf-8"))
    folios = json.load(io.open(os.path.join(bd, "_toc_pages.json"), encoding="utf-8"))
    book_title = cfg.get("head_even") or cfg.get("title_zh", "")

    runs = sorted(((v, k) for k, v in folios.items()), key=lambda x: x[0])
    opens = {f for f, _ in runs}

    log = []
    chars = set(book_title) | set("0123456789 ")
    for v in labels.values():
        chars |= set(v)
    subset = ensure_subset(cfg, chars, log)

    cjk = None
    if subset:
        try:
            pdfmetrics.registerFont(TTFont("HeadCJK", subset))
            cjk = "HeadCJK"
        except Exception as e:
            log.append("head font register failed: %s" % str(e)[:120])

    r = PdfReader(raw)
    n = len(r.pages)
    w = PdfWriter()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(float(r.pages[0].mediabox.width),
                                     float(r.pages[0].mediabox.height)))
    grey = Color(0.47, 0.45, 0.42)
    faint = Color(0.62, 0.60, 0.57)
    rule = Color(0.85, 0.83, 0.79)
    first = int(cfg.get("folio_from", FOLIO_FROM))

    for i, page in enumerate(r.pages):
        pw = float(page.mediabox.width)
        ph = float(page.mediabox.height)
        if i >= first:
            folio = i - first + 1
            c.setFillColor(grey)
            c.setFont("Times-Roman", 9.5)
            c.drawCentredString(pw / 2.0, 12.5 * MM, str(folio))
            label = head_for(folio, runs, labels, opens, book_title)
            if cjk and label:
                c.setFillColor(faint)
                c.setFont(cjk, 8.2)
                c.drawCentredString(pw / 2.0, ph - 12.5 * MM, label)
                c.setStrokeColor(rule)
                c.setLineWidth(0.4)
                c.line(pw * 0.30, ph - 15.5 * MM, pw * 0.70, ph - 15.5 * MM)
        c.showPage()
    c.save()
    buf.seek(0)
    overlay = PdfReader(buf)

    for i, page in enumerate(r.pages):
        page.merge_page(overlay.pages[i])
        w.add_page(page)
    bad = 0
    for i, page in enumerate(w.pages):
        try:
            page.compress_content_streams()
        except Exception as e:
            bad += 1
            if bad <= 2:
                log.append("compress failed on page %d: %s" % (i, str(e)[:80]))
    with open(dst, "wb") as f:
        w.write(f)

    # ---- sanity: page count and CJK text mapping -------------------------
    chk = PdfReader(dst)
    kangxi = 0
    for p in chk.pages:
        for ch in (p.extract_text() or ""):
            if 0x2F00 <= ord(ch) <= 0x2FDF:
                kangxi += 1
    log.append("pages=%d  file=%.2f MB" % (len(chk.pages),
                                           os.path.getsize(dst) / 1048576.0))
    log.append("kangxi-radical glyphs in text layer=%d %s"
               % (kangxi, "(must be 0, otherwise the PDF is not searchable)"
                  if kangxi else "(clean)"))
    common.log_to(cfg, "_stamp.txt", log)
    print("\n".join(log))


if __name__ == "__main__":
    main()
