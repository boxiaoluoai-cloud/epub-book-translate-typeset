# -*- coding: utf-8 -*-
"""Shared helpers for the EPUB translation pipeline.

Every script in this skill reads one JSON config (default: ./book.json).
All relative paths inside the config are resolved against the config file's
own directory, so a book project can live wherever the user keeps it.
"""
import io
import json
import os
import re
import sys

MARKER_RE = re.compile(r"^%%([A-Z0-9]+)%%\s*(.*)$")

DEFAULTS = {
    "src_dir": "work/src",
    "zh_dir": "work/zh",
    "out_dir": "output",
    "build_dir": "work",
    "images_subdir": "images",
    "html_name": "book.html",
    "pdf_name": "book.pdf",
    "raw_pdf": "_raw.pdf",
    "css": None,
    "parts": [],
    "units": [],
    "tail": [],
}

PATH_KEYS = ("src_dir", "zh_dir", "out_dir", "build_dir")


def config_arg(argv):
    """Return the config path from argv, or print this script's help.

    Every stage script takes the same single argument, so the help text is
    assembled here from the calling script's own docstring. One place to
    maintain, and `-h` / `--help` behaves identically on all of them.
    """
    if any(a in ("-h", "--help") for a in argv[1:]):
        doc = (getattr(sys.modules.get("__main__"), "__doc__", "") or "").strip()
        prog = os.path.basename(argv[0]) if argv else "script.py"
        print(doc)
        print()
        print("usage: python %s [book.json]" % prog)
        print()
        print("  book.json   project config. Relative paths inside it resolve")
        print("              against the config file's own directory.")
        print("              Defaults to ./book.json, or to $BOOK_CONFIG.")
        print("  -h, --help  show this message.")
        print()
        print("Docs: the skill's README.md (walkthrough) and")
        print("      references/pipeline.md (the eight-stage SOP).")
        raise SystemExit(0)
    return argv[1] if len(argv) > 1 else None


def load_config(path=None):
    """Load book.json and resolve relative directory keys against its location."""
    path = path or os.environ.get("BOOK_CONFIG") or "book.json"
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise SystemExit("config not found: %s" % path)
    cfg = dict(DEFAULTS)
    cfg.update(json.load(io.open(path, encoding="utf-8")))
    base = os.path.dirname(path)
    for k in PATH_KEYS:
        if not os.path.isabs(cfg[k]):
            cfg[k] = os.path.normpath(os.path.join(base, cfg[k]))
    cfg["_config_path"] = path
    cfg["_base"] = base
    for k in PATH_KEYS + ("out_dir",):
        os.makedirs(cfg[k], exist_ok=True)
    os.makedirs(os.path.join(cfg["out_dir"], cfg["images_subdir"]), exist_ok=True)
    return cfg


def part_map(cfg):
    """id -> part dict."""
    return {p["id"]: p for p in cfg.get("parts") or []}


def units(cfg, only=None):
    """Yield unit configs in reading order, optionally filtered by file name."""
    for u in cfg.get("units") or []:
        if only is None or u["file"] in only:
            yield u


def unit_path(cfg, name, which="zh"):
    d = cfg["zh_dir"] if which == "zh" else cfg["src_dir"]
    return os.path.join(d, name + ".md")


def read_lines(path):
    """Non-empty, stripped lines of a marker file."""
    out = []
    for ln in io.open(path, encoding="utf-8"):
        s = ln.strip()
        if s:
            out.append(s)
    return out


def parse_marker(line):
    """('TAG', value) or ('P', text) for a plain paragraph line."""
    m = MARKER_RE.match(line)
    if m:
        return m.group(1), m.group(2)
    return "P", line


def markers(path):
    """The tag sequence of a marker file (used for EN<->ZH alignment)."""
    return [parse_marker(l)[0] for l in read_lines(path)]


def cjk_count(s):
    return sum(1 for ch in s if 0x4E00 <= ord(ch) <= 0x9FFF)


def latin_words(s):
    return len([w for w in re.findall(r"[A-Za-z][A-Za-z'\-]*", s) if len(w) > 1])


def strip_markup(s):
    s = re.sub(r"%%[A-Z0-9]+%%", "", s)
    s = re.sub(r"[*_]", "", s)
    return s.strip()


def unit_display(cfg, unit, zh_lines=None):
    """Human label used in the TOC and in running heads.

    Front matter (prologue / introduction) uses the unit's own `label`, or the
    first %%H3%% heading when no label is configured.
    """
    if unit.get("front"):
        if unit.get("label"):
            return unit["label"]
        for ln in zh_lines or []:
            tag, val = parse_marker(ln)
            if tag == "H3":
                return val
        return unit.get("anchor") or unit["file"]
    title = ""
    for ln in zh_lines or []:
        tag, val = parse_marker(ln)
        if tag == "CT":
            title = val
            break
    label = unit.get("label") or unit.get("anchor") or unit["file"]
    return ("%s　%s" % (label, title)).strip("　")


def chapter_number(unit):
    """'第 10 章' -> '10'; anything else returns None."""
    m = re.search(r"第\s*(\d+)\s*章", unit.get("label") or "")
    return m.group(1) if m else None


def write_json(path, obj):
    io.open(path, "w", encoding="utf-8").write(
        json.dumps(obj, ensure_ascii=False, indent=1))


def log_to(cfg, name, lines):
    """Persist a script's report next to the other build artefacts."""
    path = os.path.join(cfg["build_dir"], name)
    io.open(path, "w", encoding="utf-8-sig").write("\n".join(lines))
    return path
