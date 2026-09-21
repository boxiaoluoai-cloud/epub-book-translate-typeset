# Chapter reading guide (chapter-front 导读)

An optional addition: a short guide placed before each chapter's body text so a
younger or less experienced reader has somewhere to stand before the argument
starts. Skip it for a specialist audience; include it when the brief mentions
students, teenagers, or "make it approachable".

## Purpose

Three jobs, in this order:

1. **概要** — say plainly what question this chapter answers and what material
   the author uses to answer it.
2. **降门槛** — pre-explain the chapter's most abstract idea in everyday
   language, so the first page does not defeat the reader.
3. **引思考** — connect the topic to the reader's own experience and close with
   1–2 questions they can actually answer.

## Hard constraints

- **Length**: 250–330 CJK characters total, in **2–3 paragraphs**.
- **Format**: one paragraph per line, each prefixed `%%GUIDE%% ` (note the
  space), inserted **after the `%%ST%%` subtitle line and before the first body
  line**. For front matter without a `%%ST%%`, insert after the last `%%H3%%`.
- Never spoil later chapters: use only this chapter's material.
- Never state anything the chapter does not support.
- No filler emotion ("让我们一起走进……"), no exclamation marks for effect.
- Address the reader as 你; refer to the author as 作者 or by surname.

## Shape

| Paragraph | Length | Content |
|---|---|---|
| 1 | 90–120 | Open with the chapter's core question, then one or two sentences on the material used: a case, an experiment, a historical figure. |
| 2 | 90–120 | The author's answer — and above all the counter-intuitive point. This is the part that makes the chapter worth reading. |
| 3 | 60–100 | Move to the reader's world (exams, choosing subjects, friendships, sport, family) and close with 1–2 specific, answerable questions. No answers given. |

## Tone

A slightly older student who has read the book, explaining it in a corridor:
plain, with judgements, not solemn, not flattering. Short sentences are fine.
Avoid academic register ("本文旨在探讨"), slogan register ("让我们一起拥抱这种能力！"),
and over-casual slang.

## Style anchor

Abstract instructions produce inconsistent guides. **Write one guide to final
quality first and put it at the end of this file as the sample**, then tell each
translator to match its register and density. A worked example beats a
specification every time.

```
%%GUIDE%% <paragraph 1>
%%GUIDE%% <paragraph 2>
%%GUIDE%% <paragraph 3>
```

## Checks

`sweep_text.py` reports paragraph count and length per unit against the
`guide` block in `book.json`:

```json
"guide": {"min_paras": 2, "max_paras": 3, "min_chars": 240, "max_chars": 360}
```

If the guides are an editorial addition, **say so on the colophon page** — the
`tail` array in `book.json` is the place. Readers should never be unsure which
words are the author's.
