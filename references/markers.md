# Marker reference

Every line of `src/<unit>.md` and `zh/<unit>.md` is one semantic block. The
prefix before the text states what kind of block it is. **The translator must
reproduce the marker sequence one-to-one** — that is what makes the alignment
check, the completeness check and the layout all work.

Translating the marker itself is never allowed. `%%FIG%%`, `%%BREAK%%` and
`%%CHAPNUM%%` keep their values verbatim.

| Marker | Meaning | Rendered as |
|---|---|---|
| `%%CHAPNUM%%` | chapter number / front-matter slug | discarded (the number is taken from config) |
| `%%CT%%` | chapter title | `.chaptitle` (h2) |
| `%%ST%%` | chapter subtitle | `.chapsub` |
| `%%H3%%` / `%%H4%%` | heading inside a chapter | h3 / h4 |
| `%%P1%%` | opening paragraph of a section, no indent | `p.noindent` |
| _no marker_ | ordinary paragraph | `p` (2em first-line indent) |
| `%%BREAK%%` | section break (a `transition` div upstream) | centred rule |
| `%%FIG%% <file>` | figure | `<figure><img>` |
| `%%CAP%%` | caption, attaches to the preceding `%%FIG%%` | `<figcaption>` |
| `%%BOXT%%` / `%%BOXI%%` / `%%ENDBOX%%` | card-style callout box | `aside.box` |
| `%%BOXIMG%% <file>` | decorative icon inside a callout | `img.boxicon` |
| `%%EXT%%` / `%%EXB%%` / `%%EXI%%` / `%%ENDEX%%` | exercise box (title / blurb / steps) | `aside.ex` |
| `%%QUOTE%%` | block quotation | `blockquote` |
| `%%EQ%%` | formula or slogan, set centred | `p.eq` (KaiTi) |
| `%%VERSE%%` | one line of verse | `.verse p.vline` |
| `%%UL%%` / `%%OL%%` | list item (unordered / ordered) | `ul` / `ol` |
| `%%GUIDE%%` | one paragraph of the chapter reading guide | `aside.guide` |
| `*text*` / `**text**` | inline emphasis | `<em>` (KaiTi) / `<strong>` |

Notes:

- Consecutive `%%GUIDE%%` lines are merged into a single `aside.guide`; the box
  closes when any other marker appears.
- `%%CAP%%` only attaches when it directly follows a `%%FIG%%`. A caption placed
  elsewhere becomes a stray `p.cap`.
- `%%VERSE%%` is not produced by the extractor (verse is hard to detect
  generically). When a book has quoted poetry, run `epub_extract.py --probe` on
  that page, find the class the publisher used, add it to `BLOCK_MAP` /
  `VERSE_CLASSES`, and re-extract. If the verse was already flattened into a
  single paragraph, split it by hand into consecutive `%%VERSE%%` lines.
- Consecutive `%%OL%%` lines become one `<ol>`; the same for `%%UL%%`. A
  `%%P1%%` or heading between them starts a new list, which is usually what the
  source intends.

## Markers whose text the renderer discards

`%%CHAPNUM%%`, `%%BREAK%%`, `%%FIG%%`, `%%ENDBOX%%`, `%%ENDEX%%`, `%%BOXIMG%%`

Anything textual absorbed onto one of these lines is **silently lost**. This is
the single most dangerous failure mode in the whole pipeline, because the file
still looks fine and the character count barely moves. `lint_markers.py` flags
it.
