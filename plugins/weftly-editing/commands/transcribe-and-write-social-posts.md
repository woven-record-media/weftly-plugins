---
description: Transcribe a local audio/video file via Weftly, then generate per-platform social media posts (LinkedIn, Reddit, Instagram, X, Bluesky) in one shot.
---

End-to-end pipeline: transcribe a local audio or video file via Weftly, then generate ready-to-paste social media posts for LinkedIn, Reddit, Instagram, X, and Bluesky from the resulting transcript. Final outputs:

- `<base>.words.json` and `<base>.srt` — the raw transcripts (per `/weftly-editing:transcribe`)
- `<base>_social_<platform>.md` — one file per selected platform, each with 2 A/B variants (per `/weftly-editing:write-social-posts`)

Input: a local file path passed as `$ARGUMENTS` (e.g., `/weftly-editing:transcribe-and-write-social-posts ~/Downloads/episode.mp4`).

This is a chained orchestrator — it does not duplicate either skill's logic. The two underlying skills are the source of truth; if their behavior changes, this skill inherits the change.

## Flags

All `/weftly-editing:write-social-posts` flags pass through:

| Flag | Description |
|------|-------------|
| `--tone {professional\|conversational\|bold\|inspirational}` | Pick tone without being asked |
| `--platforms "linkedin,reddit,instagram,x,bluesky"` | CSV subset (default: all 5) |
| `--variants {1\|2}` | Drafts per platform (default: 2) |
| `--seo "tag1,tag2,..."` | CSV topic/keyword list (max 50) |
| `--source-url URL` | CTA linkback used in posts and frontmatter |
| `--author NAME` | Override the inferred author |
| `--output-dir PATH` | Directory for social post files (default: same dir as input) |
| `--dry-run` | Print posts to stdout without writing |

## Steps

### 1. Transcribe

Execute the steps in `/weftly-editing:transcribe` against the input file. That skill handles:

- Validating the input path
- Surfacing the data retention disclosure (uploads + outputs deleted within 24h; see [weftly.ai](https://weftly.ai))
- Payment via `mppx:sign`
- Upload, polling, download
- Writing `<base>.words.json` and `<base>.srt`

If `<base>.words.json` already exists alongside the input, **ask the user whether to skip step 1** and re-use the existing transcript rather than re-paying for transcription.

If the transcribe leg fails, stop and surface the error — don't proceed to social post generation.

### 2. Write the social posts

Once `<base>.words.json` exists, execute the steps in `/weftly-editing:write-social-posts` against it. That skill walks through:

- Inferring the author (override with `--author`)
- Asking for tone (skip if `--tone` flag was passed through)
- Asking for platforms (skip if `--platforms` flag)
- Asking for SEO/topic tag list (skip if `--seo` flag)
- Tag normalization + validation (≤50, empty allowed)
- Extracting 3–5 reusable pull-hooks from the transcript
- Generating per-platform drafts (default: 2 variants each) with platform-tuned char limits, hashtag norms, and hook rules
- Writing one `<base>_social_<platform>.md` file per selected platform (or `--dry-run`)

### 3. Confirm

Print the output paths and the social post summary:

```
Raw transcript: <parent>/<base>.words.json
                <parent>/<base>.srt

Social posts:   <parent>/<base>_social_linkedin.md       (A: 1421 chars, B: 1689 chars)
                <parent>/<base>_social_reddit.md         (A: 892 chars,  B: 1104 chars)
                <parent>/<base>_social_instagram.md      (A: 1203 chars, B: 1387 chars)
                <parent>/<base>_social_x.md              (A: 247 chars,  B: 3-tweet thread)
                <parent>/<base>_social_bluesky.md        (A: 268 chars,  B: 291 chars)

  Tone: bold
  Variants per platform: 2
  Pull-hooks extracted: 4
  SEO tags used: 3 of 5
```

## Notes

- Step 1 (`transcribe`) is the only paid step; step 2 is local prompt-driven generation. If you already have a `.words.json`, run `/weftly-editing:write-social-posts` directly to skip the payment.
- Want multiple tones from the same source? Transcribe once, then run `/weftly-editing:write-social-posts` repeatedly with different `--tone` and `--output-dir` flags.
- Want a blog post AND social posts from the same transcript? Transcribe once, then run both `/weftly-editing:write-blog-post` and `/weftly-editing:write-social-posts` — neither is paid, both read the same `.words.json`.
