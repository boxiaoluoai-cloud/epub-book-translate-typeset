# -*- coding: utf-8 -*-
"""Stage 1 - extract an EPUB into one-marker-per-line markdown.

Usage
-----
    python epub_extract.py --epub book.epub --list            # spine inventory
    python epub_extract.py --epub book.epub --classes         # class usage table
    python epub_extract.py --epub book.epub --probe <doc>     # raw XHTML dump
    python epub_extract.py                                    # extract per book.json

Why this stage exists
---------------------
Everything downstream is a check against the shape of this file: the translation
brief requires a marker-for-marker copy, the layout is driven by the markers, and
completeness is verified against them. So the extractor must produce a *faithful*
marker stream for whatever book it is handed.

Adapting to an unfamiliar publisher
-----------------------------------
Publishers encode structure differently. Three mechanisms are supported, applied
in this order:

1. ``epub:type`` semantics (``chapter``, ``part``, ``subtitle``, ...) -- the
   most portable signal, used when present.
2. Class names, via the tables below. These tables are seeded with the class
   names used by Penguin Random House / Avery trade non-fiction.
3. A structural fallback: tag level plus position within the document. This is
   what carries books with no meaningful classes at all (calibre output, bare
   semantic HTML): the first heading of a document becomes the chapter title, a
   heading that is just a number becomes the chapter number, the heading right
   after it becomes the subtitle.

Run ``--classes`` on the book, then extend the tables for anything the fallback
gets wrong. Confirm by eye that a chapter now starts with ``%%CHAPNUM%%``,
``%%CT%%``, ``%%ST%%`` and then body markers.
"""
import argparse
import io
import os
import re
import sys
import zipfile
from collections import Counter
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

# ------------------------------------------------------- mechanism 2: classes
# heading class prefix -> marker
HEAD_MAP = [
    ("cn-chap-pg", "CHAPNUM"), ("bmpf", "CHAPNUM"), ("dedf", "CHAPNUM"),
    ("cst", "ST"), ("ct", "CT"),
    ("pt", "PART"), ("pn-part", "PART"),
    ("h1", "H3"), ("h3", "H3"), ("h2", "H4"), ("h4", "H4"),
]
# block class -> marker
BLOCK_MAP = {
    "qu": "QUOTE", "qu_first": "QUOTE",
    "ans": "QUOTE",
    "illcap": "CAP",
    "sp": "P1", "pf": "P1",
}
EQ_PREFIX = "eq"
QUOTE_TAGS = ("blockquote",)
QUOTE_CLASSES = ("ext", "extf", "exts", "extl", "extnlf", "pepi")
VERSE_CLASSES = ("v", "verse", "poem", "pline", "stanza")
ITALIC = {"i", "bi", "u-i", "first_ITAL"}
BOLD = {"b", "b-alt"}
SKIP_IMG = ("page_", "cover", "title_page", "next-reads", "logo", "Logo")

# --------------------------------------------------- mechanism 1: epub:type
EPUBTYPE_HEAD = {"part": "PART", "subtitle": "ST", "bridgehead": "H3",
                 "title": "CT", "chapter": "CT"}
EPUBTYPE_SKIP = {"toc", "landmarks", "page-list", "footnotes", "endnotes",
                 "bibliography", "index", "colophon", "copyright-page"}

CHAPTER_RE = re.compile(r"^\s*(chapter|part|chapitre|kapitel)\b", re.I)
NUMBER_RE = re.compile(r"^\s*(\d{1,3}|[IVXLCDM]{1,7})\s*[.、]?\s*$")
ITALIC_TAGS = ("i", "em")
BOLD_TAGS = ("b", "strong")


def M(k):
    return "%%" + k + "%%"


class Extractor(HTMLParser):
    def __init__(self, cfg, strict=True):
        super().__init__(convert_charrefs=True)
        self.cfg = cfg
        self.strict = strict     # True: class/epub:type tables only
        self.lines = []
        self.buf = []
        self.stack = []          # (tag, class, epub:type) of open elements
        self.ctx = None          # 'box' | 'ex' while inside an <aside>
        self.pending_img = None
        self.skip = 0
        self.last_break = False
        self.doc_has_ct = False  # headings already emitted in this document
        self.last_head = None
        self.prev_tag = None     # marker of the last emitted line

    # -- buffer helpers ----------------------------------------------------
    def take(self):
        t = re.sub(r"\s+", " ", " ".join(self.buf)).strip()
        t = re.sub(r"\s+([，。；：？！、）])", r"\1", t)
        self.buf = []
        return t

    def push(self, text, prefix=""):
        if not text:
            return
        line = prefix + text if prefix else text
        self.lines.append(line)
        self.last_break = False
        self._note(line)

    def raw(self, line):
        """Append a marker line that carries no text (BREAK / FIG / ENDBOX)."""
        self.lines.append(line)
        self.last_break = False
        self._note(line)

    def _note(self, line):
        m = re.match(r"%%([A-Z0-9]+)%%", line)
        self.prev_tag = m.group(1) if m else "P"

    # -- tags --------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        c = a.get("class") or ""
        etype = (a.get("epub:type") or a.get("role") or "").strip().lower()
        tag = tag.lower()
        if tag in ("head", "style", "script", "nav", "select"):
            return
        if etype in EPUBTYPE_SKIP:
            self.skip += 1
        if "transition" in c:
            self.skip += 1
            self.take()
            if not self.last_break:
                self.raw(M("BREAK"))
                self.last_break = True
        if tag == "img":
            src = os.path.basename(a.get("src", ""))
            if src.startswith(tuple(self.cfg.get("skip_img", SKIP_IMG))):
                return
            if any(x[0] == "figure" for x in self.stack):
                self.pending_img = src
            else:
                self.raw(M("FIG") + " " + src)
            return
        self.stack.append((tag, c, etype))
        if tag in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li",
                   "figcaption", "blockquote", "aside", "dd", "dt"):
            left = self.take()
            if left:
                self.push(left)
        if tag == "aside":
            self.ctx = "ex" if "box-2" in c else "box"

    def handle_endtag(self, tag):
        tag = tag.lower()
        if not self.stack:
            return
        idx = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                idx = i
                break
        if idx is None:
            return
        _, cls, etype = self.stack[idx]
        del self.stack[idx:]
        if etype in EPUBTYPE_SKIP:
            self.skip = max(0, self.skip - 1)
        if "transition" in cls:
            self.skip = max(0, self.skip - 1)
            self.take()
        if tag in ("span", "em", "strong", "b", "i", "img", "ul", "ol", "hr"):
            return
        if tag == "figcaption":
            cap = self.take()
            if self.pending_img:
                self.raw(M("FIG") + " " + self.pending_img)
                if cap:
                    self.push(cap, M("CAP") + " ")
                self.pending_img = None
            return
        if tag == "figure":
            if self.pending_img:
                self.raw(M("FIG") + " " + self.pending_img)
                self.pending_img = None
            return
        if tag == "aside":
            self.push(self.take())
            self.raw(M("ENDEX") if self.ctx == "ex" else M("ENDBOX"))
            self.ctx = None
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.emit_head(self.take(), cls, etype, tag)
            return
        if tag in ("p", "li", "div", "blockquote", "dd", "dt"):
            self.emit_block(self.take(), cls, tag)

    # -- emission rules ----------------------------------------------------
    def emit_head(self, t, cls, etype, tag):
        if not t:
            return
        mk = None
        if etype in EPUBTYPE_HEAD:
            mk = EPUBTYPE_HEAD[etype]
        if mk is None:
            for prefix, m in HEAD_MAP:
                if cls.startswith(prefix):
                    mk = m
                    break
        if mk is None:
            mk = self._infer_head(t, tag) if not self.strict else "H3"
        self.push(t, M(mk) + " ")
        self.last_head = mk
        if mk == "CT":
            self.doc_has_ct = True

    def _infer_head(self, t, tag):
        """Structural fallback: tag level plus position in the document.

        Only reached when the class tables produced no chapter title for this
        document (see the two-pass logic in main), so a book whose publisher is
        already covered by the tables is unaffected.
        """
        if NUMBER_RE.match(t) or CHAPTER_RE.match(t):
            return "CHAPNUM"
        if not self.doc_has_ct:
            return "CT"
        # A subtitle is the heading that comes immediately after the chapter
        # title, before any body text. Checked against the previous *line*, not
        # the previous heading, so a later section heading is not mistaken for
        # one.
        if self.prev_tag == self.last_head and self.last_head in ("CHAPNUM", "CT"):
            return "ST"
        return {"h1": "H3", "h2": "H3", "h3": "H4",
                "h4": "H4", "h5": "H4", "h6": "H4"}.get(tag, "H3")

    def emit_block(self, t, cls, tag):
        if not t:
            return
        c = cls.split()[0] if cls else ""
        # Some publishers put a heading's class on a <p> instead of a heading
        # tag. Off by default, because promoting classes that a book also uses
        # on body paragraphs would re-shuffle an already-extracted book. Enable
        # per book with `head_on_block` in book.json.
        if c and c in self.cfg.get("head_on_block", ()):
            self.emit_head(t, cls, "", "h3")
            return
        if self.ctx == "box":
            self.push(t, M("BOXT") + " " if c == "exth1" else M("BOXI") + " ")
            return
        if self.ctx == "ex":
            if c == "bxt":
                self.push(t, M("EXT") + " ")
            elif c.startswith("bxf"):
                self.push(t, M("EXB") + " ")
            else:
                self.push(t, M("EXI") + " ")
            return
        if c in VERSE_CLASSES:
            self.push(t, M("VERSE") + " ")
            return
        if c in BLOCK_MAP:
            self.push(t, M(BLOCK_MAP[c]) + " ")
            return
        if c.startswith(EQ_PREFIX):
            self.push(t, M("EQ") + " ")
            return
        if tag in QUOTE_TAGS or c in QUOTE_CLASSES:
            self.push(t, M("QUOTE") + " ")
            return
        if tag in ("li", "dd", "dt") or any(x[0] == "li" for x in self.stack):
            kinds = [x[0] for x in self.stack]
            self.push(t, (M("OL") if "ol" in kinds else M("UL")) + " ")
            return
        # In the fallback path, mark the paragraph that directly follows a
        # heading as a section opener (no first-line indent). Keyed off the
        # previous line, so a paragraph after a figure or quote is not caught.
        if not self.strict and (self.prev_tag is None
                                or self.prev_tag in ("CT", "ST", "PART")):
            self.push(t, M("P1") + " ")
            return
        self.push(t)

    def handle_data(self, data):
        if self.skip:
            return
        if not data.strip():
            if self.buf:
                self.buf.append(" ")
            return
        d = data.strip()
        it = any(x[0] == "span" and x[1].split()
                 and x[1].split()[0] in ITALIC for x in self.stack) \
            or any(x[0] in ITALIC_TAGS for x in self.stack)
        bd = any(x[0] == "span" and x[1].split()
                 and x[1].split()[0] in BOLD for x in self.stack) \
            or any(x[0] in BOLD_TAGS for x in self.stack)
        if it:
            d = "*" + d + "*"
        elif bd:
            d = "**" + d + "**"
        self.buf.append(d)


# ------------------------------------------------------------------ inventory
def _docs(z):
    return [n for n in z.namelist()
            if n.lower().endswith((".xhtml", ".html", ".htm"))]


def inventory(epub_path):
    z = zipfile.ZipFile(epub_path)
    roots = sorted({n.split("/")[0] for n in z.namelist() if "/" in n})
    docs = sorted(_docs(z))
    rows = ["epub: %s" % epub_path,
            "content roots: %s" % (", ".join(roots) or "(flat)"),
            "html documents: %d" % len(docs), ""]
    for n in docs:
        raw = z.read(n).decode("utf-8", "ignore")
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()
        rows.append("%8d B  %-50s %5d chars | %s"
                    % (z.getinfo(n).file_size, n.split("/")[-1], len(txt),
                       txt[:56]))
    rows.append("")
    rows.append("Next: --classes to see which class names carry the structure.")
    return "\n".join(rows)


def class_usage(epub_path, top=28):
    """The fastest way to build the class tables for a new publisher."""
    z = zipfile.ZipFile(epub_path)
    heads = Counter()
    blocks = Counter()
    classes = Counter()
    spot = {}
    for n in sorted(_docs(z)):
        raw = z.read(n).decode("utf-8", "ignore")
        for m in re.finditer(r"<(\w+)([^>]*)>([^<]{4,90})", raw):
            tag, attrs, text = m.group(1).lower(), m.group(2), m.group(3).strip()
            cm = re.search(r'class="([^"]*)"', attrs)
            c = (cm.group(1).split() or [""])[0] if cm else ""
            em = re.search(r'epub:type="([^"]*)"', attrs)
            et = em.group(1) if em else ""
            key = "<%s class=%s%s>" % (tag, c or "-", " epub:type=%s" % et if et else "")
            classes[key] += 1
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                heads[key] += 1
            elif tag in ("p", "div", "blockquote", "li", "aside", "figcaption"):
                blocks[key] += 1
            spot.setdefault(key, re.sub(r"\s+", " ", text)[:48])

    rows = ["epub: %s" % epub_path,
            "Adapt HEAD_MAP from `headings`, BLOCK_MAP / QUOTE_CLASSES / "
            "VERSE_CLASSES / ITALIC / BOLD from `blocks`.", ""]
    for title, counter in (("HEADINGS", heads), ("BLOCKS", blocks),
                           ("ALL", classes)):
        rows.append("---- %s" % title)
        for key, count in counter.most_common(top):
            rows.append("  %-42s %5d  %s" % (key, count, spot.get(key, "")))
        rows.append("")
    return "\n".join(rows)


def probe(epub_path, needle, chars):
    z = zipfile.ZipFile(epub_path)
    hit = None
    for n in z.namelist():
        stem = os.path.splitext(os.path.basename(n))[0]
        if needle in (n, stem):
            hit = n
            break
    if not hit:
        raise SystemExit("document not found: %s" % needle)
    raw = z.read(hit).decode("utf-8", "ignore")
    raw = re.sub(r"(?is)<head.*?</head>", "", raw)
    return raw[:chars]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--epub", default=None)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--classes", action="store_true")
    ap.add_argument("--probe", default=None)
    ap.add_argument("--chars", type=int, default=6000)
    args = ap.parse_args()

    if args.list or args.classes or args.probe:
        if not args.epub:
            raise SystemExit("--list/--classes/--probe need --epub <file>")
        if args.list:
            print(inventory(args.epub))
        elif args.classes:
            print(class_usage(args.epub))
        else:
            print(probe(args.epub, args.probe, args.chars))
        return

    cfg = common.load_config(args.config)
    epub = args.epub or (cfg.get("epub") or {}).get("path")
    if not epub:
        raise SystemExit("set `epub.path` in book.json (or pass --epub)")
    if not os.path.isabs(epub):
        epub = os.path.join(cfg["_base"], epub)

    mapping = (cfg.get("epub") or {}).get("units") or []
    if not mapping:
        raise SystemExit("set `epub.units` = [{file, href}, ...] in book.json "
                         "(use --list to find the hrefs)")

    z = zipfile.ZipFile(epub)
    by_stem = {os.path.splitext(os.path.basename(n))[0]: n for n in z.namelist()}
    report = []
    for item in mapping:
        unit, href = item["file"], item["href"]
        doc = href if href in z.namelist() else (
            by_stem.get(href) or by_stem.get(os.path.splitext(href)[0]))
        if not doc:
            report.append("MISS      %s  <- %s" % (unit, href))
            continue
        raw = z.read(doc).decode("utf-8", "ignore")
        raw = re.sub(r"(?is)<head.*?</head>", "", raw)
        raw = re.sub(r"(?is)<script.*?</script>", "", raw)

        # Pass 1: class tables and epub:type only, so a book whose publisher is
        # already covered extracts exactly as before.
        p = Extractor(cfg, strict=True)
        p.feed(raw)
        p.push(p.take())
        mode = "tables"
        kinds = {common.parse_marker(l)[0] for l in p.lines if l.strip()}
        if not ({"CT", "CHAPNUM"} & kinds):
            # Pass 2: no chapter structure found -- this publisher is not in the
            # tables, so fall back to tag level + document position.
            p = Extractor(cfg, strict=False)
            p.feed(raw)
            p.push(p.take())
            mode = "fallback"

        txt = re.sub(r"\n{3,}", "\n\n", "\n".join(p.lines))
        dst = common.unit_path(cfg, unit, "src")
        io.open(dst, "w", encoding="utf-8").write(txt)
        lines = common.read_lines(dst)
        kind_count = Counter(common.parse_marker(l)[0] for l in lines)
        report.append("%-26s lines=%-4d words=%-6d %-8s | %s"
                      % (unit, len(lines),
                         len(common.strip_markup(txt).split()), mode,
                         " ".join("%s:%d" % kv for kv in
                                  sorted(kind_count.items())
                                  if kv[0] != "P")[:90]))

    report.append("")
    report.append("Sanity-check the marker mix above: a chapter should show "
                  "CHAPNUM, CT, ST, then body lines.")
    report.append("Then write a per-line translation into %s, keeping the "
                  "marker sequence identical, and run check_zh.py."
                  % cfg["zh_dir"])
    common.log_to(cfg, "_report.txt", report)
    print("\n".join(report))


if __name__ == "__main__":
    main()
