---
description: Generate 2 draft social posts per platform (LinkedIn, Reddit, Instagram, X, Bluesky) from a transcript, in your chosen tone.
---

Read a transcript and generate ready-to-paste social media posts for LinkedIn, Reddit, Instagram, X, and Bluesky. **Two A/B variants per platform**, each tuned to that platform's character limit, hashtag norms, and audience expectations. **Read-only and free** — no Weftly API calls, no payment, no network.

If you don't have a transcript yet, run `/weftly-editing:transcribe <video>` first, or use `/weftly-editing:transcribe-and-write-social-posts <video>` to chain both in one shot.

Input: a path to a `.words.json` (preferred), `.srt`, or `.txt` file passed as `$ARGUMENTS` (e.g., `/weftly-editing:write-social-posts ~/Downloads/podcast.words.json`).

## Why word-level JSON helps (but isn't required)

Word-level `weftly-transcript-v2` JSON gives you per-word timestamps, which makes pull-hook timestamps precise. SRT works the same way at cue-level granularity. Plain text also works — you just lose the ability to attach timestamps to hooks.

If both `<base>.words.json` and `<base>.srt` exist, prefer the words JSON.

## Tone options

When run without `--tone`, the skill asks the user to pick one of these four:

| # | Tone | Voice |
|---|---|---|
| 1 | `professional` | Polished, third-person OK, no slang, credible framing |
| 2 | `conversational` | First-person, contractions, friendly, low-key |
| 3 | `bold` | Punchy, opinionated, contrarian hooks, short sentences |
| 4 | `inspirational` | Mission-forward, emotional, story-led, "why this matters" |

Pick the tone that matches the speaker's voice and the audience you're addressing — `professional` for a B2B founder talking to enterprise buyers, `conversational` for a podcast talking to peers, `bold` for a debate-driving thought-leadership push, `inspirational` for nonprofit / mission content.

## Per-platform rules

Each platform gets its own output file with **2 variants** (A and B), tuned to that platform's norms:

| Platform | Char target | Hashtags | Hook rule | Notes |
|---|---|---|---|---|
| `linkedin` | 1200–1800 | 3–5 at end | First line is the hook; blank line before body | Single CTA, no link-stuffing, line breaks for skim |
| `reddit` | 500–1500 | **none** | First sentence sets context, not a marketing hook | Conversational, no marketing-speak, don't sound like an ad |
| `instagram` | 800–1500 | 8–15 mixed broad+niche, end of post | First 125 chars must hook before the "more" cutoff | Add a `visual_hint` for what image/clip would pair |
| `x` | ≤280 | 1–2 max | First 100 chars carry the hook | If topic genuinely needs more room, offer a 3-tweet thread as one variant |
| `bluesky` | ≤300 | 0–2 | First sentence is the hook | No algorithmic tag boost — keep clean, conversational |

The skill enforces character ceilings per platform — if a draft exceeds the limit it must be tightened before writing.

## SEO / topic tags

`--seo "tag1,tag2,..."` is an optional comma-separated list of topic keywords. The skill uses these to:

- **Inform hashtag selection** for `linkedin`, `instagram`, `x`, `bluesky` (Reddit ignores them — no hashtags).
- **Bias word choice** in the body so the post is about the topic the user is actually trying to surface.

Empty SEO list is allowed. The skill picks hashtags from transcript context if no SEO tags are given.

### Tag validation

For the SEO list, the skill normalizes input before generating:

1. Split on commas
2. Trim whitespace per tag
3. Lowercase per tag
4. Dedupe
5. Reject if final count > 50 (with a clear error)

Surface the normalized list back to the user before generating so they can confirm.

## CLI flags

```bash
/weftly-editing:write-social-posts podcast.words.json                                          # interactive
/weftly-editing:write-social-posts podcast.words.json --tone bold                              # skip tone prompt
/weftly-editing:write-social-posts podcast.words.json --platforms "linkedin,x"                 # subset of platforms
/weftly-editing:write-social-posts podcast.words.json --variants 1                              # 1 draft per platform instead of 2
/weftly-editing:write-social-posts podcast.words.json --seo "art,community,ghana"              # inform hashtags
/weftly-editing:write-social-posts podcast.words.json --source-url https://youtu.be/...        # CTA linkback
/weftly-editing:write-social-posts podcast.words.json --output-dir ~/posts/                    # custom output dir
/weftly-editing:write-social-posts podcast.words.json --dry-run                                # print, don't write
```

| Flag | Description |
|------|-------------|
| `--tone {professional\|conversational\|bold\|inspirational}` | Pick tone without being asked |
| `--platforms "linkedin,reddit,instagram,x,bluesky"` | CSV subset (default: all 5) |
| `--variants {1\|2}` | Drafts per platform (default: 2) |
| `--seo "tag1,tag2,..."` | CSV topic/keyword list (max 50 after dedupe). Empty allowed. |
| `--source-url URL` | URL used as the CTA linkback in posts (and `source_video_url` in frontmatter) |
| `--author NAME` | Override the inferred author |
| `--output-dir PATH` | Directory for output files (default: same dir as input) |
| `--dry-run` | Print posts to stdout without writing files |

## Workflow

### 1. Locate and read the transcript

If `$ARGUMENTS` is empty, list candidates and ask:

```bash
ls *.words.json *.srt *.txt 2>/dev/null
```

For `.words.json`, read the `segments` array (and `words` if you need precise pull-hook timestamps).
For `.srt`, read the cue blocks.
For `.txt`, read the whole text.

### 2. Infer author (default)

Try to identify the speaker(s) from the transcript:
- Title or filename hints (e.g., `daniel_kerkhoff_interview.words.json` → Daniel Kerkhoff)
- The first ~30 lines often introduce the speaker ("We're here with X" / "Welcome, Y")
- **Co-hosted formats** introduce two or more speakers in the opening (e.g. "my name is X and this is The Show, and I'm Y"). When you see this pattern, capture **all** named speakers, not just the first one.

Surface the inferred author(s) for confirmation. Override with `--author` if the user provides it.

`--author` accepts either a single name (`"Daniel Kerkhoff"`) or a comma-separated list (`"Mike Lagerquist, Becki True"`). The frontmatter `author` field is rendered as a string for solo speakers or as a `&`-joined string for co-hosts (`Mike Lagerquist & Becki True`).

### 3. Ask for tone (if no `--tone` flag)

Present the 4 numbered options from the table above. Accept either the number or the name.

### 4. Ask for platforms (if no `--platforms` flag)

Prompt: *"Which platforms? (comma-separated from: linkedin, reddit, instagram, x, bluesky — press Enter for all 5):"*

Normalize, validate against the allowed set, dedupe. Show the final list back.

### 5. Ask for SEO tags (if no `--seo` flag)

Prompt: *"Comma-separated topic keywords for hashtag selection (≤50; press Enter to skip):"*

Normalize and validate. Show the cleaned list back.

### 6. Extract pull-hooks from the transcript

Pick **3–5 strong 1-sentence quotes** from the transcript that could serve as hook material across platforms. The same anti-fabrication rules from `/weftly-editing:write-blog-post` apply:

- **Single contiguous run from the source.** Each pull-hook must be one uninterrupted span of words from the transcript — one cue, or adjacent cues whose text reads naturally when joined. **Never stitch non-adjacent fragments.**
- **Drawn from the source, not invented.** Body prose may paraphrase; pull-hooks must be the speaker's actual words.
- **Spelling: prefer the speaker's own spelling over the transcriber's.** If the speaker spells their own name or a brand name aloud somewhere in the transcript (e.g. `K-E-R-K-H-O-F-F`), use that spelling everywhere — even if the auto-transcription rendered it differently. Same rule for any other proper noun that's clearly mis-transcribed but verifiable from context.
- **Filler at the boundary may be trimmed without elision** — if the verbatim text starts with "uh" or "like" and you skip it, that's fine without an ellipsis.

These hooks are reusable raw material — variants for X / Bluesky may quote one near-verbatim; LinkedIn / Instagram may build a longer post around one.

### 7. Generate drafts per platform

For each selected platform, generate the requested number of variants (default 2). For each variant:

- Match the chosen **tone** (voice from the table).
- Respect the platform's **character target** and **hashtag norms** (table above).
- Respect the platform's **hook rule** — first N chars must earn the click.
- For Reddit: **no hashtags, no marketing-speak.** If a draft sounds like an ad, rewrite it. Reddit communities downvote promotional tone hard.
- For Instagram: include a `visual_hint` line (separate from the post body) suggesting what image, clip, or graphic would pair — e.g. "Close-up of speaker mid-sentence at 2:26" or "Behind-the-scenes shot from the festival".
- For X: if the topic genuinely cannot fit in 280 chars, **variant B may be a 3-tweet thread** (numbered 1/3, 2/3, 3/3). Variant A must always be a single tweet ≤280.
- If `--source-url` is set, include it as a CTA on `linkedin`, `instagram`, `x`, `bluesky`. **Reddit: do not include the URL inline** — communities flag self-promotion. Instead, include it as a one-line "Source:" footer at the very end of the post, separated by a blank line, so the user can paste it into the Reddit "URL" field if submitting as a link post or remove it for text posts.

**Quote rules inside post bodies:**

- **Verbatim or contiguous** — every word inside a single set of quote marks must appear in the source as a contiguous run.
- **No silent stitching of non-adjacent fragments.** If you want to combine two phrases the speaker said in different parts of the transcript, render them as **two separate quoted phrases** in your prose, not as one quote with the gap hidden.
- **Visible elision only.** If you trim mid-quote, signal it with an ellipsis or a clearly broken second quote — never with an em-dash that disguises the cut.

### 8. Validate character counts

For each draft, count characters (including spaces, hashtags, and any inline URL).

- If a variant **exceeds** its platform ceiling, tighten it and re-count. Do not ship a draft over the limit.
- If a variant lands **far below** the target band (e.g. a 200-char LinkedIn post when the target is 1200–1800), expand it with material from the transcript rather than padding.

**Measure the count, do not estimate it.** Use a real character counter (e.g. `python3 -c 'import sys; print(len(sys.stdin.read()))'` against the variant body, or `wc -m` minus 1 for the trailing newline) on the exact text you are about to write. Eyeballed estimates routinely come in 5–10% off, which is fine for soft target bands but can put a draft silently over a hard ceiling (X 280, Bluesky 300). Both the inline `[N chars, M hashtags]` line under each variant heading and the `char_count` value in frontmatter must reflect the measured number.

### 9. Write one file per platform

Output filename pattern: `<base>_social_<platform>.md` in the input's parent directory (or `--output-dir`).

Examples:
- `podcast_social_linkedin.md`
- `podcast_social_reddit.md`
- `podcast_social_instagram.md`
- `podcast_social_x.md`
- `podcast_social_bluesky.md`

Only write files for platforms the user actually selected. If `--dry-run`, print all drafts to stdout instead.

### 10. Print summary

```
Wrote ~/path/to/podcast_social_linkedin.md       (A: 1421 chars, B: 1689 chars)
      ~/path/to/podcast_social_reddit.md         (A: 892 chars,  B: 1104 chars)
      ~/path/to/podcast_social_instagram.md      (A: 1203 chars, B: 1387 chars)
      ~/path/to/podcast_social_x.md              (A: 247 chars,  B: 3-tweet thread)
      ~/path/to/podcast_social_bluesky.md        (A: 268 chars,  B: 291 chars)

  Tone: bold
  Variants per platform: 2
  Pull-hooks extracted: 4
  SEO tags used: 3 of 5
```

## Output file shape

Each per-platform file has YAML frontmatter + an H2 per variant. Example for `podcast_social_linkedin.md`:

```markdown
---
platform: linkedin
tone: bold
author: Daniel Kerkhoff
date_drafted: 2026-05-06
source_transcript: ../path/to/podcast.words.json
source_video_url: https://youtu.be/abc123
seo_tags: [art residency, community art, ghana]
variants:
  - id: A
    char_count: 1421
    hashtags: [#ArtResidency, #CommunityArt, #Ghana, #CreativeExchange]
  - id: B
    char_count: 1689
    hashtags: [#ArtResidency, #CulturalExchange, #Ghana]
pull_hooks_used:
  - text: "We had a big festival last fall in Ghana where I just wanted everyone in the village to celebrate creativity."
    timestamp: "02:26"
    used_in: [A]
  - text: "They're my homes now."
    timestamp: "01:54"
    used_in: [B]
---

## Variant A

[1421 chars, 4 hashtags]

The hook line that grabs in the first 200 chars goes here.

Body content here, hitting LinkedIn norms — line breaks, scannable, single CTA at the end…

Watch the full conversation: https://youtu.be/abc123

#ArtResidency #CommunityArt #Ghana #CreativeExchange

---

## Variant B

[1689 chars, 3 hashtags]

A different hook angle — same source material, different framing for A/B testing…

Watch: https://youtu.be/abc123

#ArtResidency #CulturalExchange #Ghana
```

Instagram files additionally include a `visual_hint` field per variant in the frontmatter (e.g. `visual_hint: "Close-up of speaker mid-sentence at 2:26"`) and as a comment under each variant heading.

X files: if variant B is a thread, render it as three numbered code blocks under `## Variant B (thread)`, each labeled with its char count.

Reddit files: omit `hashtags` from frontmatter (it's always empty). Include a trailing `Source: <url>` footer in the body if `--source-url` is set, separated by a blank line.

Co-hosted content: render `author` in frontmatter as a `&`-joined string (e.g. `author: Mike Lagerquist & Becki True`). Don't try to encode it as a YAML list — downstream tools that read frontmatter expect a string here.

## Notes

- This skill is conversational and prompt-driven — there's no Python script. All generation happens in-context.
- Per-platform character ceilings are **hard limits**, not guidance. A 285-char tweet doesn't post.
- Per-platform character targets (the bands like 1200–1800 for LinkedIn) are guidance — landing slightly outside is fine if the post reads better.
- Pull-hooks are reusable raw material across variants and platforms. The same hook can anchor an X post and a LinkedIn post — that's the point of A/B drafts and multi-platform reuse.
- If you want to remix the same source with a different tone, run the skill again with a different `--tone` and `--output-dir`. Each run produces a fresh set of files; the original transcript stays untouched.
- For Reddit specifically: the drafts are **starting points**, not "post this verbatim." Reddit communities have wildly different cultures — always read the subreddit's top 10 posts before pasting. The skill cannot infer subreddit norms.
