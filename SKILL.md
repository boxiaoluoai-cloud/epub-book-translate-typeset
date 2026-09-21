---
name: epub-book-translate-typeset
description: "Translates a foreign-language EPUB end to end into Chinese and produces a print-ready typeset edition: a single-file HTML plus a PDF with cover, table of contents carrying real folios, running heads, figures, captions and callout boxes. Use when a user asks to translate a whole book from an .epub file, to turn a translated draft into a printable edition, or to add chapter-front reading guides for students. Covers structure-preserving extraction, parallel per-chapter translation driven by a shared brief, completeness and fidelity checks, HTML/PDF rendering with the machine's own headless Chrome, folio stamping with a subset CJK font, and the font-stack trap that silently breaks a PDF text layer. Triggers: 翻译这本 epub, 整书翻译并排版, epub 转中文 PDF, 排版便于打印, 给各章加导读, translate this epub into Chinese, make a printable Chinese PDF from an epub."
agent_created: true
---

# EPUB book translation and typesetting

Turn **any** foreign-language EPUB into a Chinese, print-ready HTML + PDF
edition. The skill is book-agnostic: the book lives in one JSON config file, the
scripts are generic, and the two things that genuinely depend on the publisher —
which CSS classes carry the structure, and which Latin words the book keeps
inline — are per-book settings rather than hard-coded assumptions.

The whole method rests on one decision made at the start: **extract the book into
a line-per-block format where the line prefix names the kind of block**
(`%%CT%%` for a chapter title, `%%QUOTE%%` for a quotation, `%%EXT%%`/`%%EXI%%`
for an exercise box, and so on). Everything else follows from it — parallel
translation with a mechanical self-check, layout, completeness verification, and
page numbers.

Working without that structure, by contrast, makes the pieces untestable: you
cannot tell an omitted sentence from a reworded one, and you cannot lay out
boxes, verse or captions reliably.

## What varies per book, and what never does

- **Always per book**: title / subtitle / author / colophon text, the unit list,
  the part divisions, the `file` → `href` mapping of EPUB documents, and the
  terminology table inside the translation brief.
- **Sometimes per book**: extend the extractor's class tables (run `--classes`
  once, copy what you see), `skip_img` prefixes for decorative plates,
  `head_on_block` if the publisher puts a heading's class on a `<p>`,
  `latin_allow` for words the book keeps untranslated, `css` for a different look.
- **Never per book**: the scripts, the marker vocabulary, the stylesheet, the
  check logic.

## When to use

- A request to translate an `.epub` (or a translated draft) into Chinese and deliver
  something printable.
- A request to typeset an existing Chinese book draft into HTML/PDF with a TOC,
  running heads and folios.
- A request to add chapter-front guides for students or young readers.

Not for: single articles, subtitling, or translating text that is not a
structured book.

## Setup

1. Copy `assets/book.json` next to the book project and fill it in. Every script
   takes that file as its only argument, and resolves relative paths against it.
2. Install the Python dependencies used by the render and stamp stages:
   `pip install pymupdf pypdf reportlab fonttools playwright`, then
   `python -m playwright install chromium` is **not** needed — the scripts drive
   the Chrome or Edge already installed on the machine.
3. Read `references/pipeline.md`. It is the operational checklist and the place
   where the expensive mistakes are documented.

Every stage script accepts `--help`, which prints its own usage; only
`epub_extract.py` takes `--epub` / `--classes` / `--probe` instead of the config
file as its first argument.

## Workflow

Run these in order, reading the reports between steps and fixing the source files
rather than patching the output.

| Stage | Command | What it establishes |
|---|---|---|
| 1 Extract | `epub_extract.py --list` → `--classes` → `--probe <doc>` → (extract) | The marker files. `--classes` is the one pass that tells you whether this publisher needs the class tables extended. |
| 2 Translate | one agent per unit | `zh/<unit>.md`, marker-for-marker with `src/<unit>.md`. Give every agent the same brief. |
| 3 Check | `check_zh.py`, `lint_markers.py`, `ratio_check.py` | Nothing omitted, markers aligned, no text absorbed into a discarded marker. |
| 4 Sweep | `sweep_text.py` | Quotes, punctuation, typos, guide length. |
| 5 Build | `build_html.py` | The single-file HTML. |
| 6 Render | `html_to_pdf.py` → `toc_pages.py` → `build_html.py` → `html_to_pdf.py` → `toc_pages.py` → `stamp.py` | PDF with a TOC carrying real folios and with running heads. Re-run until `toc_pages.py` reports `STABLE`. |
| 7 Verify | `verify_pdf.py` | Every translated paragraph is present in the PDF. |
| 8 Deliver | clean `out_dir` to deliverables + `images/` | HTML and PDF. |

Two stages are non-negotiable:

- **Stage 1** produces the structure that makes every later check possible.
- **Stage 3** is the only place omission is caught. Word counts do not catch it;
  a paragraph swallowed by a discarded marker changes the count by a rounding
  error while deleting real content.

## Translating in parallel

Fill in `references/translation-guide.md` for the book — terminology table,
punctuation and marker rules, the ratio self-check — and hand the *same file* to
every translator agent, one agent per unit, about five at a time. Tell each agent
its unit's core argument, its hard names, and which special markers occur in it.
The brief is what keeps fourteen independently translated chapters reading like
one book.

If agents are rate-limited, fall back to translating yourself, unit by unit, and
read the Chinese as a book rather than as a line-by-line mapping.

## Reading guides

For a student or general audience, add a short guide before each chapter's body
text — two or three `%%GUIDE%%` paragraphs that state the chapter's question,
give the author's answer (especially the counter-intuitive part), then turn to
the reader with one or two answerable questions. `references/guide-spec.md` has
the constraints and the rationale for writing a style sample first.

Guides are an editorial addition: record that fact on the colophon page via the
config's `tail` entries.

## Reference files

- `references/pipeline.md` — the eight stages in detail, with the pitfalls that
  cost the most time (newline-eating regexes, alignment drift, the CJK font
  stack that maps characters to Kangxi radicals, `merge_page` stream growth,
  `clone_from` font duplication, cross-references to untranslated matter).
- `references/markers.md` — every marker, what it renders to, and the markers
  whose textual content is discarded.
- `references/translation-guide.md` — the brief template to fill in per book.
- `references/guide-spec.md` — the chapter-front guide specification.
- `assets/print.css` — the print stylesheet; override per book with the `css`
  config key.
- `assets/book.json` — annotated configuration template.

## Non-negotiables

- Reproduce the marker sequence one-to-one. Never translate a marker, never merge
  or split lines without recording the reason.
- Assert `kangxi-radical glyphs = 0` on the stamped PDF; otherwise the text layer
  is unsearchable even though the pages look right.
- Do not silently drop source material. If an appendix, quiz or index is left
  untranslated, say so on the colophon page and rewrite any in-text pointer to
  it.
