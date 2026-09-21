#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 5 - build a print-ready single-file HTML edition from the marker files.

Reads every ``zh/<unit>.md`` in reading order plus ``book.json`` and writes:

  <out_dir>/<html_name>          the book, one file, images referenced relatively
  <build_dir>/_labels.json       anchor -> display label (TOC / running heads)
  <build_dir>/_toc_pages.json    read back if present, so TOC folios can be
                                 back-filled on a second pass (see toc_pages.py)

The marker -> HTML mapping is documented in references/markers.md.
Style lives in assets/print.css and can be overridden per book with the
config key ``css``.

Usage:  python build_html.py [book.json]
"""
import html
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

SHELL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>{{TITLE}}</title>
<style>{{CSS}}</style>
</head>
<body>
<div id="book">
<section class="titlepage">
  <h1 class="zh">{{TITLE}}</h1>
  <p class="sub">{{SUBTITLE}}</p>
  <div class="rule"></div>
  <p class="by">{{AUTHOR}}</p>
  <p class="orig">{{ORIGINAL}}</p>
</section>

<section class="tocpage">
  <h2>{{TOC_TITLE}}</h2>
  <ul id="toc">{{TOC}}</ul>
</section>

{{BODY}}

<section class="tail">
  <div class="rulebig"></div>
{{TAIL}}
</section>
</div>
</body>
</html>
"""


def em(t):
    """Inline emphasis: **bold** first, then *italic*."""
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", t)
    return t


def esc(t):
    return html.escape(t, quote=False)


class Builder:
    def __init__(self, cfg):
        self.cfg = cfg
        self.img = cfg["images_subdir"]
        self.toc_pages = {}
        p = os.path.join(cfg["build_dir"], "_toc_pages.json")
        if os.path.exists(p):
            try:
                self.toc_pages = io.open(p, encoding="utf-8").read()
                import json
                self.toc_pages = json.loads(self.toc_pages)
            except Exception:
                self.toc_pages = {}

    # ---------------------------------------------------------------- TOC line
    def tocli(self, cls, anchor, text):
        pg = self.toc_pages.get(anchor)
        body = '<a href="#%s">%s</a>' % (anchor, text)
        if pg:
            body += '<span class="dots"></span><span class="pg">%s</span>' % pg
        return '<li class="%s">%s</li>' % (cls, body)

    # ------------------------------------------------------------------ a unit
    def build_unit(self, unit):
        path = common.unit_path(self.cfg, unit["file"], "zh")
        lines = common.read_lines(path)
        out = []
        title = sub = None
        state = {"box": False, "ex": False, "guide": False, "list": None}
        fig = {"src": None, "cap": None}
        notes = []

        def close_open():
            o = []
            for key in ("box", "ex", "guide"):
                if state[key]:
                    o.append("</aside>")
                    state[key] = False
            if state["list"]:
                o.append({"ul": "</ul>", "ol": "</ol>", "verse": "</div>"}
                         .get(state["list"], "</ol>"))
                state["list"] = None
            return o

        def flush_fig(cap=None):
            src = fig["src"]
            if not src:
                return
            cap = fig["cap"] if cap is None else cap
            if cap:
                out.append('<figure><img src="%s/%s" alt="%s"/>'
                           '<figcaption>%s</figcaption></figure>'
                           % (self.img, src, esc(cap), em(esc(cap))))
            else:
                out.append('<figure><img src="%s/%s" alt=""/></figure>'
                           % (self.img, src))
            fig["src"], fig["cap"] = None, None

        for line in lines:
            tag, val = common.parse_marker(line)
            if tag not in ("FIG", "CAP"):
                flush_fig()

            if tag == "CHAPNUM":
                continue
            elif tag == "CT":
                title = val
            elif tag == "ST":
                sub = val
            elif tag == "BREAK":
                out += close_open()
                out.append('<div class="break">—</div>')
            elif tag == "GUIDE":
                if not state["guide"]:
                    out += close_open()
                    out.append('<aside class="guide"><p class="gtitle">%s</p>'
                               % esc(self.cfg.get("guide_label", "导读")))
                    state["guide"] = True
                out.append('<p class="gp">%s</p>' % em(esc(val)))
            elif tag == "FIG":
                out += close_open()
                flush_fig()
                fig["src"] = val
            elif tag == "CAP":
                if fig["src"]:
                    flush_fig(val)
                else:
                    fig["cap"] = val
            elif tag == "BOXT":
                out += close_open()
                out.append('<aside class="box"><h4 class="boxt">%s</h4>'
                           % em(esc(val)))
                state["box"] = True
            elif tag == "BOXIMG":
                out.append('<img class="boxicon" src="%s/%s" alt=""/>'
                           % (self.img, val))
            elif tag == "BOXI":
                out.append('<p class="boxi">%s</p>' % em(esc(val)))
            elif tag == "ENDBOX":
                out += close_open()
            elif tag == "EXT":
                out += close_open()
                out.append('<aside class="ex"><h4 class="ext">%s</h4>'
                           % em(esc(val)))
                state["ex"] = True
            elif tag == "EXB":
                out.append('<p class="exb">%s</p>' % em(esc(val)))
            elif tag == "EXI":
                # NOTE: must not call close_open() here -- these steps live
                # inside the exercise <aside> opened by EXT.
                if state["list"] != "ulex":
                    out.append('<ol class="exlist">')
                    state["list"] = "ulex"
                out.append('<li>%s</li>' % em(esc(val)))
            elif tag == "ENDEX":
                out += close_open()
            elif tag == "QUOTE":
                out += close_open()
                out.append('<blockquote>%s</blockquote>' % em(esc(val)))
            elif tag == "EQ":
                out += close_open()
                out.append('<p class="eq">%s</p>' % em(esc(val)))
            elif tag == "VERSE":
                if state["list"] != "verse":
                    out += close_open()
                    out.append('<div class="verse">')
                    state["list"] = "verse"
                out.append('<p class="vline">%s</p>' % em(esc(val)))
            elif tag in ("H3", "H4"):
                out += close_open()
                out.append('<h3>%s</h3>' % em(esc(val)) if tag == "H3"
                           else '<h4>%s</h4>' % em(esc(val)))
            elif tag == "UL":
                if state["list"] != "ul":
                    out += close_open()
                    out.append("<ul>")
                    state["list"] = "ul"
                out.append("<li>%s</li>" % em(esc(val)))
            elif tag == "OL":
                if state["list"] != "ol":
                    out += close_open()
                    out.append("<ol>")
                    state["list"] = "ol"
                out.append("<li>%s</li>" % em(esc(val)))
            elif tag == "P1":
                out += close_open()
                out.append('<p class="noindent">%s</p>' % em(esc(val)))
            else:
                if re.match(r"\*\d+\s", val):          # footnote marker
                    notes.append(val)
                    continue
                out += close_open()
                out.append("<p>%s</p>" % em(esc(val)))

        out += close_open()
        flush_fig()
        if notes:
            out.append('<div class="notes">')
            for n in notes:
                out.append('<p class="note">%s</p>' % em(esc(n)))
            out.append("</div>")
        return title, sub, "\n".join(out)

    # ------------------------------------------------------------------- whole
    def build(self):
        cfg = self.cfg
        pmap = common.part_map(cfg)
        body, toc, labels = [], [], {}
        current_part = None
        part_orn = cfg.get("part_ornament")
        chap_orn = cfg.get("chapter_ornament")

        for unit in common.units(cfg):
            pid = unit.get("part")
            if pid and pid != current_part:
                current_part = pid
                part = pmap.get(pid) or {}
                num = part.get("num", "")
                ptitle = part.get("title", "")
                pen = part.get("en", "")
                inner = ""
                if part_orn:
                    inner += '<img class="partbar" src="%s/%s" alt=""/>' % (self.img, part_orn)
                inner += ('<p class="partnum">%s</p><h2 class="parttitle">%s</h2>'
                          '<p class="parten">%s</p>' % (num, ptitle, pen))
                body.append('<section class="part" id="%s"><div class="partinner">%s'
                            '</div></section>' % (pid, inner))
                toc.append(self.tocli("tocpart", pid, "%s　%s" % (num, ptitle)))
                labels[pid] = ("%s　%s" % (num, ptitle)).strip("　")

            anchor = unit.get("anchor") or unit["file"]
            title, sub, inner = self.build_unit(unit)
            label = unit.get("label") or ""
            if unit.get("front"):
                head = '<h2 class="fronttitle">%s</h2>' % esc(label)
                toc.append(self.tocli("tocfront", anchor, esc(label)))
                labels[anchor] = label or (title or "")
            else:
                num = common.chapter_number(unit) or ""
                head = ('<p class="chapnum">%s</p><h2 class="chaptitle">%s</h2>'
                        % (num, em(esc(title or ""))))
                text = ("%s　%s" % (label, title or "")).strip("　")
                toc.append(self.tocli("tocch", anchor, esc(text)))
                labels[anchor] = text
            if sub:
                head += '<p class="chapsub">%s</p>' % em(esc(sub))
            if chap_orn:
                head += '<img class="orn" src="%s/%s" alt=""/>' % (self.img, chap_orn)
            body.append('<section class="chapter" id="%s"><header>%s</header>%s'
                        '</section>' % (anchor, head, inner))

        tail = "\n".join("  <p>%s</p>" % t for t in cfg.get("tail") or [])
        css_path = cfg.get("css")
        if css_path and not os.path.isabs(css_path):
            css_path = os.path.join(cfg["_base"], css_path)
        if not css_path:
            css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "assets", "print.css")
        css = io.open(os.path.normpath(css_path), encoding="utf-8").read()

        out_html = (SHELL
                    .replace("{{CSS}}", css)
                    .replace("{{TOC}}", "\n".join(toc))
                    .replace("{{BODY}}", "\n".join(body))
                    .replace("{{TAIL}}", tail)
                    .replace("{{TOC_TITLE}}", cfg.get("toc_title", "目　录"))
                    .replace("{{TITLE}}", esc(cfg.get("title_zh", "")))
                    .replace("{{SUBTITLE}}", esc(cfg.get("subtitle_zh", "")))
                    .replace("{{AUTHOR}}", esc(cfg.get("author_zh", "")))
                    .replace("{{ORIGINAL}}", cfg.get("original", "")))
        dst = os.path.join(cfg["out_dir"], cfg["html_name"])
        io.open(dst, "w", encoding="utf-8").write(out_html)
        common.write_json(os.path.join(cfg["build_dir"], "_labels.json"), labels)
        return dst, len(out_html), labels


def main():
    cfg = common.load_config(common.config_arg(sys.argv))
    dst, size, labels = Builder(cfg).build()
    print("html: %s (%d chars)" % (dst, size))
    print("labels: %d anchors" % len(labels))
    if not Builder(cfg).toc_pages:
        print("note: no _toc_pages.json yet -- TOC numbers will be filled in "
              "after toc_pages.py runs once")


if __name__ == "__main__":
    main()
