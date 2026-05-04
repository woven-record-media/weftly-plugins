---
description: Read a timestamped transcript and recommend 30–60 second intro hook candidates with timestamps and rationale.
---

Analyze a timestamped transcript and recommend the strongest 30–60 second segments for use as an intro hook clip. This skill is **read-only and free** — it makes no Weftly API calls, runs no ffmpeg, and produces no video. It just reads a transcript and proposes hook candidates with start/end timestamps you can hand to a clip-extraction step (manual ffmpeg, `extract_clip`, or any other cutter).

If you don't have a transcript yet, run `/weftly-editing:transcribe <video>` first.

Input: a path to a `.words.json` (preferred) or `.srt` file passed as `$ARGUMENTS` (e.g., `/weftly-editing:identify-intro-clip ~/Downloads/podcast.words.json`).

## Why word-level JSON is preferred

Word-level `weftly-transcript-v2` JSON includes a `words` array with millisecond-precise start/end times for every word. That lets you snap recommended clip boundaries to clean **word boundaries** — no clipping mid-word. SRT works as a fallback but only gives you segment-level (caption-line) timestamps, which can land mid-phrase.

If both `<base>.words.json` and `<base>.srt` exist next to each other, prefer the words JSON.

## What makes a strong intro hook

Score each candidate on these criteria. The recommendations you surface should be the segments that hit multiple criteria — not just any 30–60s window.

- **Surprising data or claim** that creates curiosity ("wait, really?"). Numbers, percentages, counterintuitive statements.
- **Emotional or mission-aligned moments** that connect with viewers — passion, conviction, a personal anecdote, a clear stake.
- **Strong opening line** — the first sentence the viewer hears must grab attention. A flat "So, um, today we're talking about..." is not a hook even if the rest is good. The candidate's *first* words matter.
- **Complete thought arcs** — never cut mid-sentence or mid-thought. The clip must stand alone if a viewer drops in cold.
- **Tease, don't resolve** — the best hooks raise a question or promise a payoff that the rest of the video delivers. If the clip fully answers its own question, the viewer has no reason to keep watching.

Hard constraints:

- **Duration: 30–60 seconds.** Under 30s rarely lands enough context; over 60s loses retention.
- **Boundaries: snap to clean word starts/ends** (from the `words` array if available). Don't clip mid-word.
- **Avoid filler-heavy openings.** If the candidate's first 3–5 seconds are "um, uh, you know, so I think...", pick a different start point or a different candidate.

## Workflow

### 1. Locate the transcript

If `$ARGUMENTS` is empty, list candidates in the working directory and ask the user which file to analyze:

```bash
ls *.words.json *.srt 2>/dev/null
```

Prefer `.words.json` over `.srt` if both exist for the same base name.

### 2. Read the transcript

For **`weftly-transcript-v2` JSON**:

- Read the `segments` array to scan for candidate ranges (each segment is a sentence-ish caption block with `start`, `end`, and `text`).
- Use the `words` array for word-boundary snapping when picking exact `start`/`end` timestamps.

For **SRT**:

- Read the cue blocks. Each cue gives you a `start --> end` and the line text. Use cue boundaries as your snap points (you cannot snap finer than a cue without word-level data).

### 3. Identify and rank candidates

Find **2–3 candidate segments** that hit multiple criteria above. For each candidate:

- Pick a `start` time that snaps to the beginning of a strong opening sentence (not mid-thought, not on a filler).
- Pick an `end` time that snaps to a complete thought boundary, with total duration in [30s, 60s].
- If using `.words.json`, snap both timestamps to actual word boundaries from the `words` array. Note which words those are.

Rank candidates by how strongly they hit the criteria — the top one should be your recommended pick.

### 4. Present recommendations

For each candidate, surface to the user:

- **Rank** (1, 2, 3)
- **Start / end timestamps** in `M:SS.ms` format (e.g. `0:11.5 → 1:14.2`)
- **Duration** in seconds
- **Transcript excerpt** — the actual words of the clip, verbatim
- **Why it works** — 1–2 sentences citing which criteria it hits (surprising claim, emotional moment, strong opener, etc.)
- **Caveats** — anything that could be a problem (e.g., "starts with a slight 'so'", "ends on a question that's resolved 30s later")

### 5. (Optional) Write candidates to disk

If the user wants to feed the recommendations into a downstream tool, offer to write a `<base>_intro_candidates.json` next to the input. Schema:

```json
{
  "source": "podcast.words.json",
  "source_format": "weftly-transcript-v2",
  "candidates": [
    {
      "rank": 1,
      "start": "0:11.5",
      "end": "1:14.2",
      "duration_seconds": 62.7,
      "excerpt": "Verbatim transcript text of the clip...",
      "rationale": "Opens with a surprising stat (X% of...) and lands on an emotional close.",
      "caveats": null
    }
  ]
}
```

Only write the file if the user asks for it — by default this skill is conversational and surfaces the picks in chat.

## Notes

- This skill is purely read-and-recommend. It does **not** cut video, write a clip, or call any paid API. To actually extract the recommended clip, hand the timestamps to your clip-cutter of choice (manual ffmpeg, the Weftly `extract_clip` tool on a video that's already been processed by `find_clips`, etc.).
- For a paid clip-discovery tool that scores candidates server-side and returns ranked ranges *plus* the source video staying in Weftly storage for cheap downstream cuts, see Weftly's `find_clips` ($2.00) — that's the right call when you want algorithmic scoring across a whole video and plan to extract several clips. This local skill is the right call when you already have a transcript and want a quick conversational read on intro candidates without spending anything.
- Word-boundary snapping matters: if you recommend `start: 0:11.5` and the nearest word boundary is `0:11.42`, surface `0:11.42`. The downstream cutter will thank you.
- If the transcript is shorter than 90 seconds total, say so plainly — there isn't enough material to pick from.
