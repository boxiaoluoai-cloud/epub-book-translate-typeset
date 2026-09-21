# Pipeline SOP

Eight stages. Do not skip stage 1 or stage 3 — they are what make the rest
possible.

```
0  recon        ask about scope + deliverables; size the book
1  extract      epub -> src/<unit>.md         (one marker per line)
2  translate    src/*.md -> zh/*.md           (parallel, shared brief)
3  check        check_zh / lint_markers / ratio_check
4  sweep        sweep_text                    (quotes, typos, guide stats)
5  build        build_html                    -> single-file HTML
6  render       html_to_pdf -> toc_pages -> build_html -> html_to_pdf -> stamp
7  verify       verify_pdf                    (every paragraph must be present)
8  deliver      clean the output dir, present HTML + PDF
```

Run every script with the project's config file:

```
python scripts/<script>.py path/to/book.json
```

---

## 0. Recon

Two questions decide everything else; ask them in one go:

1. **Scope.** Whole book including front/back matter, or body only? An English
   index is meaningless once translated — offer to drop it or turn it into a
   bilingual term list. Name what you are leaving out and say so on the colophon.
2. **Deliverable.** Print-ready HTML alone, HTML + PDF, or those plus an
   editable `.docx`.

Then size the book. Split it so each unit is **3,000–7,000 English words**;
about fourteen units translate well in parallel. Record the per-unit line and
word counts from stage 1 — they are the baseline for every later check.

## 1. Extract

```
python scripts/epub_extract.py --epub book.epub --list
python scripts/epub_extract.py --epub book.epub --classes
python scripts/epub_extract.py --epub book.epub --probe 007_c002_Chapter_1 4000
```

`--list` gives an inventory of spine documents with a text preview; `--classes`
tabulates which `(tag, class, epub:type)` combinations carry the structure, with
a sample of each; `--probe` dumps the raw XHTML of one document. Put the `file` ->
`href` mapping in `book.json` under `epub.units`, then run the extractor with no
arguments to write every `src/<unit>.md`.

### Adapting to an unfamiliar publisher

Structure is recovered from three signals, in this order:

1. `epub:type` semantics (`chapter`, `part`, `subtitle`, `bridgehead`).
2. Class names, via the tables at the top of `epub_extract.py`. Those tables are
   seeded with Penguin Random House / Avery class names.
3. A structural fallback (tag level plus position in the document), used per
   document when the first two find no chapter title at all. This is what makes
   a class-less book — calibre output, bare semantic HTML — extract at all.

The extractor runs pass 1 with the tables only, and re-runs pass 2 with the
fallback only for documents that yielded no `%%CT%%` or `%%CHAPNUM%%`. A book
already covered by the tables therefore extracts exactly as it did before, which
keeps it safe to re-extract an in-progress project.

For a new publisher: run `--classes`, extend `HEAD_MAP` / `BLOCK_MAP` /
`QUOTE_CLASSES` / `VERSE_CLASSES` / `ITALIC` / `BOLD` with what you see, then
re-extract. Confirm by eye that a chapter begins `%%CHAPNUM%%`, `%%CT%%`,
`%%ST%%` and then body markers — a chapter file whose first lines are all `%%H3%%`
means the tables did not match.

Per-book knobs (in `book.json`, not in the script):

| key | why you would set it |
|---|---|
| `skip_img` | filename prefixes of decorative plates (`page_`, `cover`, a publisher logo) that should not become figures |
| `head_on_block` | class names your publisher puts on a `<p>` rather than a heading tag |
| `latin_allow` | Latin words this book deliberately keeps inline, so `check_zh.py` stops flagging them |

If a book quotes poetry, look for the verse class and add it to `VERSE_CLASSES`;
see `markers.md`.

## 2. Translate

Fill in `references/translation-guide.md` for this book — terminology table,
publisher names, punctuation rules, marker rules, self-check definition — and
give **the same file** to every translator. Launch one agent per unit, in
batches (large batches tend to hit rate limits; five at a time is practical).

Each agent's prompt needs: read the brief first; input and output absolute
paths; the chapter's core argument; the traps (hard-to-translate names, the
special markers present in this unit, how many boxes or figures it has); and
the requirement to report line counts in and out.

Keep each unit's translation in its own file: `zh/<unit>.md`. Never let two
agents write the same file.

**If agents are rate-limited**, the fallback is to do it yourself, unit by unit.
It is slower but works; read the Chinese as a book rather than as a line-by-line
mapping, and consult the English only where the Chinese reads oddly.

## 3. Check

```
python scripts/check_zh.py      book.json   # completeness, markers, latin leakage
python scripts/lint_markers.py  book.json   # structure, lost-text markers, guides
python scripts/ratio_check.py   book.json   # per-line omission candidates
```

Read the reports, fix the files, re-run until clean. `ratio_check.py` is a
triage tool, not a verdict: a long English paragraph split into two Chinese
paragraphs shows up as a low ratio on one line and a high one on the next, which
is harmless. A line whose Chinese is a third of the English is worth reading.

## 4. Sweep

```
python scripts/sweep_text.py book.json
```

Fix ASCII quotes, doubled punctuation, lines that begin with a closing quote,
and unbalanced parentheses. If guides are in play, check the paragraph count and
length it reports.

## 5. Build the HTML

```
python scripts/build_html.py book.json
```

Writes `<out_dir>/<html_name>`, plus `_labels.json` (anchor → display label) and
reads `_toc_pages.json` when it exists. Style lives in `assets/print.css`;
override per book with the `css` key.

Structural decision worth making once: put the plates — cover, part dividers,
chapter ornaments, figures — in `<out_dir>/images/` and reference them relatively
so the folder is self-contained.

## 6. Render, locate, re-render, stamp

```
python scripts/html_to_pdf.py  book.json   # first pass, TOC has no folios
python scripts/toc_pages.py    book.json   # locate unit openings
python scripts/build_html.py   book.json   # back-fill the TOC
python scripts/html_to_pdf.py  book.json
python scripts/toc_pages.py    book.json   # expect: convergence=STABLE
python scripts/stamp.py        book.json   # folios + running heads
```

If `toc_pages.py` reports `CHANGED` on the second run, the TOC shifted the
pagination; run the pair again. Two passes converge in practice. Anything that
reports `MISS` means a needle did not match — usually a title with a character
the extractor normalised, or a unit whose opening page does not begin with the
expected text.

Order matters in `stamp.py`: one overlay document for all pages, subset the
running-head font, `PdfWriter()` + `add_page`, then
`compress_content_streams()` on the writer's pages. Each of those is a 3–10×
size difference; the docstring explains why.

## 7. Verify

```
python scripts/verify_pdf.py book.json
```

Every paragraph in `zh/*.md` must appear in the rendered PDF. A few misses are
paragraphs straddling a page break; a run of misses means content is being
dropped by a marker or a style rule. This is the check that catches what word
counts cannot.

Also confirm from `stamp.py` output that `kangxi-radical glyphs = 0`. If it is
not zero, the PDF's text layer is not searchable and the font stack needs
changing — see below.

## 8. Deliver

Leave the output directory with exactly the deliverables plus `images/`, and
keep every intermediate in `work/`. Present the HTML (it previews in the
browser) and the PDF.

---

## Pitfalls that cost the most time

**A regex cleanup that eats newlines.** A "tidy up the spacing" pass using
`re.sub(r"\s+", " ", text)` over a whole file joins paragraphs and drags markers
into the middle of lines. In marker-per-line formats, never let `\s` match
across lines. Fixing it afterwards means re-splitting text on sentence
boundaries against the source — real work, entirely avoidable.

**Extra ZH lines must not consume EN lines.** Any alignment script (marker
comparison, ratio check) has to treat ZH-only caption lines and guide paragraphs
as insertions. Otherwise the pairing drifts by one from the insert point onwards
and the report fills with false alarms.

**CJK font stacks can destroy the text layer.** In this environment
`Source Han Serif SC` / `Noto Serif CJK SC` caused Chinese characters to be
mapped to Kangxi radical codepoints (U+2F00–U+2FDF) in the PDF — visually fine,
but copy and paste produced nonsense and search failed. Use a plain
Songti/SimSun body, Heiti/SimHei headings, Kaiti/KaiTi for emphasis, and assert
that the Kangxi count is zero. Detection is one line:

```python
sum(1 for p in doc for ch in p.get_text() if 0x2F00 <= ord(ch) <= 0x2FDF)
```

**`merge_page` leaves streams uncompressed.** Without
`compress_content_streams()` a 4 MB book becomes 13 MB.

**`clone_from` duplicates shared fonts.** Build the writer with `PdfWriter()`
and `add_page`; `PdfWriter(clone_from=...)` copied the body fonts on every page
in testing.

**Reportlab embeds the CJK font per overlay document.** Draw all pages into one
canvas, and subset the font to the running-head characters first.

**Cross-references to matter you did not translate.** If the source says "see
the diagnostic quiz at the back" and the edition omits the quiz, rewrite the
sentence to say where it lives in the original. Leaving it produces a reference
to nothing.

**Paragraph breaks vs line counts.** A faithful translation may split a very long
English paragraph into two Chinese ones. Decide this deliberately and allow for
it in the checks rather than fighting it.

## Windows and shell notes

- The Bash tool may lack coreutils on Windows; use PowerShell.
- `Get-Content` in Windows PowerShell 5.1 decodes UTF-8-without-BOM files as the
  system ANSI codepage and prints mojibake. The file is fine — read it with an
  explicit `-Encoding UTF8` or with the Read tool.
- Have Python scripts write their own report files (`encoding="utf-8-sig"`)
  instead of relying on shell redirection, which may produce UTF-16.
- Deletions go through the Recycle Bin and can fail; harmless unreferenced
  assets can simply be left in place.
