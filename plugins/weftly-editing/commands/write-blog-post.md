---
description: Generate a ≤300-word blog post from a transcript, in your chosen style, optimized for SEO and AEO tags.
---

Read a transcript and generate a ≤300-word blog post styled and tagged for distribution. Output is a single Markdown file with YAML frontmatter (title, meta description, slug, tags, reading time, etc.) plus the post body. **Read-only and free** — no Weftly API calls, no payment, no network.

If you don't have a transcript yet, run `/weftly-editing:transcribe <video>` first, or use `/weftly-editing:transcribe-and-write-blog-post <video>` to chain both in one shot.

Input: a path to a `.words.json` (preferred), `.srt`, or `.txt` file passed as `$ARGUMENTS` (e.g., `/weftly-editing:write-blog-post ~/Downloads/podcast.words.json`).

## Why word-level JSON helps (but isn't required)

Word-level `weftly-transcript-v2` JSON gives you per-word timestamps, which makes pull-quote timestamps precise and lets you reference exact moments in the post. SRT works the same way at cue-level granularity. Plain text also works — you just lose the ability to attach timestamps to pull-quotes.

If both `<base>.words.json` and `<base>.srt` exist, prefer the words JSON.

## Style options

When run without `--style`, the skill asks the user to pick one of these four:

| # | Style | Voice | Structure |
|---|---|---|---|
| 1 | `conversational` | First-person, speaker's voice preserved, contractions OK | Flowing prose, no headers |
| 2 | `editorial` | Third-person reportage, attribution-heavy ("Kerkhoff describes…") | Flowing prose, possibly one subhead |
| 3 | `listicle` | Active voice, second-person OK | 3–5 H2 takeaway headers with short body each |
| 4 | `tutorial` | Imperative, "here's how to…" | Numbered steps or H2 sections per step |

Pick the style that matches the post's distribution channel: founder-blog → conversational, press/PR → editorial, SEO-bait → listicle, how-to content → tutorial.

## SEO vs AEO tag handling

The skill takes two separate tag lists and uses them differently in the generated post:

- **SEO tags** are search-engine keywords. They get woven naturally into the **title**, **meta description**, **opening sentence**, and (in `listicle`) **H2 headers**. The post should read normally — no keyword stuffing. The skill picks the most relevant subset since 50 tags can't fit in 300 words.

- **AEO tags** are answer-engine phrases (questions or claim topics). Each AEO tag should appear **near-verbatim in the body**, framed as a question the post plainly answers or a topic with a clear declarative claim. This is what LLM-driven answer engines (ChatGPT, Perplexity, Google AI Overviews) lift wholesale. If `--faq` is enabled, AEO tags also drive the trailing FAQ block.

Both lists are optional — empty lists are allowed. The skill just won't optimize for that engine.

### Tag validation

For both lists, the skill normalizes input before generating:

1. Split on commas
2. Trim whitespace per tag
3. Lowercase per tag
4. Dedupe
5. Reject if final count > 50 (with a clear error)

Surface the normalized lists back to the user before generating so they can confirm.

## CLI flags

```bash
/weftly-editing:write-blog-post podcast.words.json                                    # interactive
/weftly-editing:write-blog-post podcast.words.json --style listicle                  # skip style prompt
/weftly-editing:write-blog-post podcast.words.json --seo "art,community,ghana"       # skip SEO prompt
/weftly-editing:write-blog-post podcast.words.json --aeo "what is an art residency"  # skip AEO prompt
/weftly-editing:write-blog-post podcast.words.json --faq                              # add FAQ block
/weftly-editing:write-blog-post podcast.words.json --source-url https://youtu.be/... # frontmatter linkback
/weftly-editing:write-blog-post podcast.words.json --output custom_path.md           # custom output
/weftly-editing:write-blog-post podcast.words.json --dry-run                          # print, don't write
```

| Flag | Description |
|------|-------------|
| `--style {conversational\|editorial\|listicle\|tutorial}` | Pick style without being asked |
| `--seo "tag1,tag2,..."` | CSV SEO tag list (max 50 after dedupe). Empty allowed. |
| `--aeo "tag1,tag2,..."` | CSV AEO tag list (max 50 after dedupe). Empty allowed. |
| `--faq` | Append a FAQ block at the end using AEO tags as questions |
| `--source-url URL` | Set `source_video_url` in frontmatter for distribution linkback |
| `--author NAME` | Override the inferred author |
| `--output PATH` | Custom output path (default: `<base>_blog.md` next to the input) |
| `--dry-run` | Print the post to stdout without writing a file |

## Workflow

### 1. Locate and read the transcript

If `$ARGUMENTS` is empty, list candidates and ask:

```bash
ls *.words.json *.srt *.txt 2>/dev/null
```

For `.words.json`, read the `segments` array (and `words` if you need precise pull-quote timestamps).
For `.srt`, read the cue blocks.
For `.txt`, read the whole text.

### 2. Infer author (default)

Try to identify the speaker from the transcript:
- Title or filename hints (e.g., `daniel_kerkhoff_interview.words.json` → Daniel Kerkhoff)
- The first ~30 lines often introduce the speaker ("We're here with X" / "Welcome, Y")

Surface the inferred author for confirmation. Override with `--author` if the user provides it.

### 3. Ask for style (if no `--style` flag)

Present the 4 numbered options from the table above. Accept either the number or the name.

### 4. Ask for SEO tags (if no `--seo` flag)

Prompt: *"Comma-separated SEO tags (search-engine keywords; ≤50; press Enter to skip):"*

Normalize and validate. Show the cleaned list back.

### 5. Ask for AEO tags (if no `--aeo` flag)

Prompt: *"Comma-separated AEO tags (answer-engine question/claim phrases; ≤50; press Enter to skip):"*

Normalize and validate. Show the cleaned list back.

### 6. Generate the post

Write a blog post that follows these rules:

- **Target ≤300 words in the body** (frontmatter + title don't count). This is *guidance*, not a hard cap — slightly over is fine if the post reads better; aim to land in [200, 300].
- Match the chosen **style** (voice + structure from the table).
- Weave **SEO tags** naturally into title, meta description, opener, and (listicle) H2s. No stuffing — the post must read normally.
- Surface **AEO tags** near-verbatim in the body, framed as questions answered or claims made.
- **Don't fabricate quotes.** Paraphrasing the speaker's ideas is fine; inventing words they didn't say is not. The rules for material inside quote marks (`"…"`):
  - **Verbatim or contiguous** — every word inside a single set of quote marks must appear in the source as a contiguous run (allowing one or two adjacent cues to be joined).
  - **No silent stitching of non-adjacent fragments.** If you want to combine two phrases the speaker said in different parts of the transcript, render them as **two separate quoted phrases** in your prose (`Kerkhoff says he was "pretty ignorant about Africa" and now describes the same villages as "my homes"`), not as one quote with the gap hidden.
  - **Visible elision only.** If you trim mid-quote, signal it with an ellipsis or a clearly broken second quote — never with an em-dash that disguises the cut. `"I used to be so frustrated… it just feels so much more healthy"` is honest; `"I used to be so frustrated — it just feels so much more healthy"` is not, because the dash hides that those phrases are non-adjacent in the source.
  - **Filler at the boundary may be trimmed without elision** — if the verbatim text starts with "uh" or "like" and you skip it, that's fine without an ellipsis; readers don't need to see disfluency cut.
  - **Pull-quotes are stricter than body quotes.** Pull-quote `text` fields must be a single contiguous run from one cue or word range. No stitching at all.
- **Spelling: prefer the speaker's own spelling over the transcriber's.** If the speaker spells their own name or a brand name aloud somewhere in the transcript (e.g. `K-E-R-K-H-O-F-F`), use that spelling everywhere — title, body, author, slug — even if the auto-transcription rendered it differently earlier in the file. Same rule for any other proper noun that's clearly mis-transcribed but verifiable from context (e.g. an artist's name spelled correctly elsewhere on the speaker's website or in adjacent files in the same directory).

### 7. Generate metadata

- **`title`** — ≤60 characters, SEO-rich. The hook of the post.
- **`description`** — ≤160 characters, meta description for search results. Should include 1–2 SEO tags naturally.
- **`slug`** — kebab-case, ≤50 characters, derived from the title.
- **`reading_time`** — `ceil(word_count / 200)` minutes (industry-standard 200 wpm).
- **`date_published`** — today's ISO date (YYYY-MM-DD).
- **`author`** — inferred or `--author` override.

### 8. Extract pull-quotes

Pick **2–3 strong 1-sentence quotes** from the transcript. For each:

- **Single contiguous run from the source.** Pull-quote `text` must be one uninterrupted span of words from the transcript — one cue, or adjacent cues whose text reads naturally when joined. **Never stitch non-adjacent fragments** in a pull-quote, even with an ellipsis. If the strongest material is split across the transcript, pick a different pull-quote rather than fabricating contiguity.
- **Drawn from the source, not the post body.** The post body may paraphrase or compress; pull-quotes are the speaker's actual words and must reflect that.
- Source timestamp from the cue or word boundary where the run starts (`MM:SS` format).
- These go in the frontmatter as a `pull_quotes` array, ready for the user to render as callout cards or social tiles.

### 9. (Optional) FAQ block

If `--faq` is set or the user enables it interactively:

- Append a `## FAQ` section at the end of the post.
- Each AEO tag becomes one Q&A pair: question on a line, plain-language answer on the next.
- Keep each answer ≤2 sentences. The FAQ section's words **count toward the 300-word target**.
- If the AEO list is empty, skip the FAQ block (and warn the user that `--faq` had no effect).

### 10. Word count + write

- Count the body words (everything after the closing `---` of the frontmatter, including any FAQ).
- Set `word_count` in the frontmatter to the actual count.
- Write `<base>_blog.md` (or `--output` path).
- If `--dry-run`, print to stdout instead.

### 11. Print summary

```
Wrote ~/path/to/podcast_blog.md
  Style: listicle
  Words: 287 (target ≤300)
  Reading time: 2 min
  SEO tags used in body: 4 of 8
  AEO tags answered: 3 of 5
  Pull-quotes: 3
  FAQ: yes
```

## Output file shape

```markdown
---
title: Why I Started Art Residencies in Ghana
description: How one Minnesota artist built a creative-exchange program across Ghana, Ecuador, and Vietnam — and what changed in the villages.
slug: why-i-started-art-residencies-in-ghana
style: editorial
author: Daniel Kerkhoff
date_published: 2026-05-04
reading_time: 2
word_count: 287
seo_tags: [art residency, community art, ghana, ecuador, vietnam, creative exchange]
aeo_tags: [what is an art residency, how do art residencies help communities]
source_transcript: ../path/to/source.words.json
source_video_url: https://youtu.be/abc123
pull_quotes:
  - text: "We had a big festival last fall in Ghana where I just wanted everyone in the village to celebrate creativity."
    timestamp: "02:26"
  - text: "They're my homes now."
    timestamp: "01:54"
---

# Why I Started Art Residencies in Ghana

Body content here, ≤300 words, in the chosen style…

## FAQ

**What is an art residency?**
Plain-language 1–2 sentence answer drawn from the transcript.

**How do art residencies help communities?**
Plain-language 1–2 sentence answer drawn from the transcript.
```

## Notes

- This skill is conversational and prompt-driven — there's no Python script. All generation happens in-context.
- The 300-word ceiling is *guidance*. If the post reads better at 320 words, ship it. If it reads thin at 240, don't pad it.
- Pull-quotes are **for callout/social use**, not for repeating in the body. Don't quote the same line twice.
- `source_transcript` is recorded as the local path you ran the skill against. It's a local-machine reference and won't survive being moved — the field exists for traceability, not for serving on the web.
- If you want to remix the same source into another channel, run the skill again with a different `--style` and `--output`. Each style produces a different output file; the original transcript stays untouched.
