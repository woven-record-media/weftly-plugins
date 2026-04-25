---
description: Remove filler words and false starts from a Weftly word-level transcript to tighten pacing.
---

Remove filler words and false starts from a Weftly word-level transcript (`weftly-transcript-v2` JSON) to tighten pacing without losing meaningful content. Outputs a cleaned `<base>_cleaned.words.json` and a regenerated `<base>_cleaned.srt` alongside the input.

If you don't have a transcript yet, run `/weftly-editing:transcribe <file>` first, or use `/weftly-editing:transcribe-and-remove-fillers <file>` to chain both in one shot.

Input: a path to a `.words.json` file passed as `$ARGUMENTS` (e.g., `/weftly-editing:remove-fillers ~/Downloads/podcast.words.json`).

## Prerequisites

- **Python 3.8+** (stdlib only — no pip packages, no ffmpeg, no external services).

## Locating the script

The Python script ships inside this plugin at `plugins/weftly-editing/scripts/remove_fillers.py`. Locate it dynamically rather than hard-coding a path — the plugin install location varies:

```bash
SCRIPT="$(find "$HOME/.claude/plugins" -type f -path '*weftly-editing/scripts/remove_fillers.py' -print -quit)"
if [ -z "$SCRIPT" ]; then
  echo "Could not locate remove_fillers.py inside the installed weftly-editing plugin." >&2
  exit 1
fi
```

Use `"$SCRIPT"` in the invocations below.

## What counts as a filler

- **Single-word fillers:** Um, Uh, Hmm, Mm, Ah, Oh, Er, Eh (and doubled variants like Umm, Uhh, Mmm, Ahh, Ohh)
- **Short phrase fillers:** "you know", "I mean", "like", "so", "right", "okay", "ok"
- **False starts:** Segments with 3 or fewer words ending with a comma (heuristic for incomplete thoughts)

All matching is case-insensitive and allows trailing punctuation (commas, periods, ellipses).

## How the gap threshold works

When a filler segment is removed, the script checks the gap between the previous meaningful segment's end and the next meaningful segment's start. The filler is only removed if this gap exceeds the threshold (default: 1.0 second). This prevents removing fillers that would leave unnaturally tight gaps between spoken phrases.

- **Lower threshold** (e.g., 0.5s) — more aggressive removal
- **Higher threshold** (e.g., 2.0s) — more conservative; only removes fillers with large surrounding gaps

## CLI reference

```bash
python3 "$SCRIPT" input.words.json                     # clean fillers, write outputs
python3 "$SCRIPT" input.words.json --dry-run           # preview removals without writing
python3 "$SCRIPT" input.words.json --threshold 1.5     # custom gap threshold (default: 1.0s)
python3 "$SCRIPT" input.words.json --output clean.words.json  # custom output path
python3 "$SCRIPT" input.words.json --no-false-starts   # only remove pure filler words
```

| Flag | Description |
|------|-------------|
| `--dry-run` | Preview removals without writing output |
| `--threshold SECONDS` | Minimum gap to allow filler removal (default: 1.0s) |
| `--output PATH` | Custom output words JSON path (an SRT sibling is always written next to it) |
| `--no-false-starts` | Disable false start detection; only remove pure filler words |

## Workflow

1. Run with `--dry-run` first so the user can see which segments would be removed and the gap each removal would leave.
2. Adjust `--threshold` if the user wants more or fewer removals.
3. Re-run without `--dry-run` to write the cleaned outputs.

## Notes

- Original timestamps are preserved on the kept content (no time-shifting) — this is a transcript cleanup, not a video re-encode.
- Both outputs are re-indexed: segments and SRT entries are renumbered sequentially after removal.
- Default outputs land next to the source: `<base>_cleaned.words.json` and `<base>_cleaned.srt`.
- Words inside removed segments are also dropped from the output `words` array; words outside removed segments are preserved as-is.
- If you point the script at a hand-written or legacy `.srt` file (no words JSON), it will fail with a clear error. The skill's contract is words-JSON in. To process an SRT directly, transcribe with `/weftly-editing:transcribe` first to produce the canonical words JSON, then run this skill against it.
