# -*- coding: utf-8 -*-
"""Stage 6 - render the HTML to PDF with the machine's own Chrome / Edge.

No Chromium download is needed: any Chromium-family browser already installed
works. Two execution paths are supported and tried in order:

  1. Playwright driving the local browser binary. This is the reliable path --
     it honours the stylesheet's @page size and margins, and it really renders
     the print media query.
  2. `chrome --headless=new --print-to-pdf` as a fallback when Playwright is
     absent. Modern Chrome honours @page here too, but it is less controllable.

Usage:  python html_to_pdf.py [book.json]
"""
import io
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

WIN_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]
POSIX_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/usr/bin/microsoft-edge",
]


def find_browser(cfg):
    explicit = cfg.get("browser")
    if explicit and os.path.exists(explicit):
        return explicit
    for c in WIN_CANDIDATES + POSIX_CANDIDATES:
        if c and os.path.exists(c):
            return c
    for name in ("chrome", "google-chrome", "chromium", "msedge", "microsoft-edge"):
        w = shutil.which(name)
        if w:
            return w
    return None


def via_playwright(exe, src, dst, timeout_ms):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe,
                              args=["--no-sandbox", "--disable-gpu"])
        pg = b.new_page()
        pg.goto("file:///" + src.replace("\\", "/"))
        pg.wait_for_timeout(timeout_ms)
        pg.emulate_media(media="print")
        pg.pdf(path=dst, format="A4", print_background=True,
               margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
               prefer_css_page_size=True)
        b.close()


def via_cli(exe, src, dst):
    cmd = [exe, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
           "--print-to-pdf=" + dst, "file:///" + src.replace("\\", "/")]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.STDOUT, timeout=600)


def main():
    cfg = common.load_config(common.config_arg(sys.argv))
    src = os.path.join(cfg["out_dir"], cfg["html_name"])
    dst = os.path.join(cfg["out_dir"], cfg.get("raw_pdf", "_raw.pdf"))
    if not os.path.exists(src):
        raise SystemExit("run build_html.py first: %s not found" % src)

    exe = find_browser(cfg)
    log = ["html: %s" % src, "browser: %s" % (exe or "NOT FOUND")]
    if not exe:
        raise SystemExit("no Chrome/Edge found -- set `browser` in book.json")

    try:
        import playwright  # noqa: F401
        via_playwright(exe, src, dst, int(cfg.get("render_wait_ms", 3000)))
        log.append("path: playwright (css page size honoured)")
    except ImportError:
        via_cli(exe, src, dst)
        log.append("path: chrome --print-to-pdf (playwright not installed)")
    except Exception as e:
        log.append("playwright failed: %s" % str(e)[:200])
        via_cli(exe, src, dst)
        log.append("path: chrome --print-to-pdf (fallback)")

    log.append("raw pdf: %s (%d bytes)" % (dst, os.path.getsize(dst)))
    common.log_to(cfg, "_pdf_log.txt", log)
    print("\n".join(log))


if __name__ == "__main__":
    main()
