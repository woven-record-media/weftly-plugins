# `weftly-editing` examples

Sample inputs you can run the editing skills against without needing to transcribe a real file first.

## `sample.words.json`

A made-up 31-second `weftly-transcript-v2` transcript of a fictional podcast intro about shipping fast vs. quality. Demonstrates the canonical word-level format that every `weftly-editing` skill consumes:

```json
{
  "format": "weftly-transcript-v2",
  "segments": [ { "index": 1, "start": 0.0, "end": 2.78, "text": "..." }, ... ],
  "words":    [ { "word": "Hi", "start": 0.05, "end": 0.25 }, ... ]
}
```

- `format` is always the literal string `weftly-transcript-v2`.
- `segments` are sentence-ish caption blocks with second-precision start/end times. They mirror what shows up in the matching `.srt`.
- `words` carries per-word timestamps from Whisper. Use this array when snapping clip boundaries to clean word edges.

Authoritative schema: <https://api.weftly.ai/.well-known/weftly-transcript-v2.schema.json>

## What the sample contains

- **7 segments**, ~31 seconds total
- **82 words** with monotonic non-decreasing timestamps
- Realistic disfluencies: `um,`, `you know,`, comma-trailing pauses (so you can demo `/weftly-editing:remove-fillers` against it)
- A clear thesis (~"speed and quality reinforce each other") with a strong opening line — enough material to demo `/weftly-editing:identify-intro-clip`
- Enough narrative arc (problem → claim → first concrete tactic) that `/weftly-editing:write-blog-post` can produce a meaningful ≤300-word post

## Try it

From this directory:

```bash
# Identify hook candidates (free, read-only)
/weftly-editing:identify-intro-clip ./sample.words.json

# Remove fillers (free, local Python script)
/weftly-editing:remove-fillers ./sample.words.json --dry-run

# Generate a blog post (free, prompt-driven)
/weftly-editing:write-blog-post ./sample.words.json --style listicle --seo "ship faster,test suite,quality engineering"
```

## Validating the schema

If you want to confirm the file matches the published schema, you can fetch and validate it with any JSON Schema validator. For example, with `ajv-cli`:

```bash
curl -s https://api.weftly.ai/.well-known/weftly-transcript-v2.schema.json -o /tmp/v2.schema.json
ajv validate -s /tmp/v2.schema.json -d sample.words.json
```

## Note on the sample

This is a hand-crafted, fictional transcript — the speaker doesn't exist and no audio file is associated with it. Real Whisper output will have small irregularities the sample doesn't (occasional `[Music]` markers, very short word durations, the rare reversed-timestamp from speaker overlap) but the structural shape is the same.
