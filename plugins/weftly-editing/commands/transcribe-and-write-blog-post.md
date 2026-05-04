---
description: Transcribe a local audio/video file via Weftly, then generate a ≤300-word blog post from the transcript in one shot.
---

End-to-end pipeline: transcribe a local audio or video file via Weftly, then generate a styled, tagged blog post from the resulting transcript. Final outputs:

- `<base>.words.json` and `<base>.srt` — the raw transcripts (per `/weftly-editing:transcribe`)
- `<base>_blog.md` — the blog post with YAML frontmatter and body (per `/weftly-editing:write-blog-post`)

Input: a local file path passed as `$ARGUMENTS` (e.g., `/weftly-editing:transcribe-and-write-blog-post ~/Downloads/episode.mp4`).

This is a chained orchestrator — it does not duplicate either skill's logic. The two underlying skills are the source of truth; if their behavior changes, this skill inherits the change.

## Flags

All `/weftly-editing:write-blog-post` flags pass through:

| Flag | Description |
|------|-------------|
| `--style {conversational\|editorial\|listicle\|tutorial}` | Pick style without being asked |
| `--seo "tag1,tag2,..."` | CSV SEO tag list (max 50) |
| `--aeo "tag1,tag2,..."` | CSV AEO tag list (max 50) |
| `--faq` | Append a FAQ block at the end |
| `--source-url URL` | `source_video_url` in frontmatter |
| `--author NAME` | Override the inferred author |
| `--output PATH` | Custom blog output path |
| `--dry-run` | Print the post to stdout without writing |

## Steps

### 1. Transcribe

Execute the steps in `/weftly-editing:transcribe` against the input file. That skill handles:

- Validating the input path
- Surfacing the data retention disclosure (uploads + outputs deleted within 24h; see [weftly.ai](https://weftly.ai))
- Payment via `mppx:sign`
- Upload, polling, download
- Writing `<base>.words.json` and `<base>.srt`

If `<base>.words.json` already exists alongside the input, **ask the user whether to skip step 1** and re-use the existing transcript rather than re-paying for transcription.

If the transcribe leg fails, stop and surface the error — don't proceed to blog generation.

### 2. Write the blog post

Once `<base>.words.json` exists, execute the steps in `/weftly-editing:write-blog-post` against it. That skill walks through:

- Inferring the author (override with `--author`)
- Asking for style (skip if `--style` flag was passed through)
- Asking for SEO tag list (skip if `--seo` flag)
- Asking for AEO tag list (skip if `--aeo` flag)
- Tag normalization + validation (≤50 each, empty allowed)
- Generating the post body (≤300 words target), title, description, slug
- Extracting 2–3 pull-quotes
- Optional FAQ block (`--faq`)
- Writing `<base>_blog.md` (or `--output`)

### 3. Confirm

Print the output paths and the blog summary:

```
Raw transcript: <parent>/<base>.words.json
                <parent>/<base>.srt
Blog post:      <parent>/<base>_blog.md
  Style: listicle
  Words: 287
  Reading time: 2 min
  SEO tags used: 4 of 8
  AEO tags answered: 3 of 5
  Pull-quotes: 3
  FAQ: yes
```

## Notes

- Step 1 (`transcribe`) is the only paid step; step 2 is local prompt-driven generation. If you already have a `.words.json`, run `/weftly-editing:write-blog-post` directly to skip the payment.
- Want multiple styles from the same source? Transcribe once, then run `/weftly-editing:write-blog-post` repeatedly with different `--style` and `--output` flags.
