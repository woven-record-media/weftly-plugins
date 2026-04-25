---
description: Extract a short intro hook clip from a source video, matched to a target file's encoding for clean concat splicing.
---

Extract a 30–60 second intro hook clip from a source video, matched to a target file's encoding settings so the output can be spliced via concat demuxer (stream copy). Also extracts and time-shifts matching transcript content from a Weftly word-level transcript (`weftly-transcript-v2` JSON), writing a clipped `.srt` and a clipped `.words.json` next to the trimmed video.

If you don't have a transcript yet, run `/weftly-editing:transcribe <video>` first, or use `/weftly-editing:transcribe-and-intro-clip <video>` to chain both in one shot.

## Prerequisites

This skill shells out to system tools — they are **not** bundled with the plugin:

- **Python 3.10+** (stdlib only; no pip packages).
- **`ffprobe`** — used to inspect codec / encoding properties of source and target files.
- **`ffmpeg`** — used to extract the clip with matched encoding.

Both `ffprobe` and `ffmpeg` ship together in the standard ffmpeg distribution. If they aren't on `PATH`, install via:

- macOS: `brew install ffmpeg`
- Debian / Ubuntu: `sudo apt install ffmpeg`
- Fedora: `sudo dnf install ffmpeg`
- Windows: `winget install ffmpeg` (or [ffmpeg.org](https://ffmpeg.org/download.html))

Verify with `ffmpeg -version` and `ffprobe -version` before running this skill. If either is missing, the script will fail with a clear "ffmpeg/ffprobe not found" error before any encoding work starts.

## Locating the script

The Python script ships inside this plugin at `plugins/weftly-editing/scripts/intro_clip.py`. Locate it dynamically rather than hard-coding a path:

```bash
SCRIPT="$(find "$HOME/.claude/plugins" -type f -path '*weftly-editing/scripts/intro_clip.py' -print -quit)"
if [ -z "$SCRIPT" ]; then
  echo "Could not locate intro_clip.py inside the installed weftly-editing plugin." >&2
  exit 1
fi
```

Use `"$SCRIPT"` in the invocations below.

## Workflow

### Step 1: Discover files

List video and transcript files in the working directory:

```bash
ls *.mp4 *.MP4 *.mov *.MOV *.words.json *.srt 2>/dev/null
```

Ask the user which video to extract from and which file to match encoding settings to (the target video the hook will be spliced onto).

### Step 2: Probe files

Probe source and target videos to verify properties:

```bash
python3 "$SCRIPT" --probe-files source.mp4 target.mp4
```

### Step 3: Read transcript & identify hook

Read the words JSON. Use the `segments` array to locate candidate hook ranges and the `words` array to snap the chosen `start`/`end` to clean word boundaries (no clipping mid-word).

Identify the strongest 30–60 second segment for an intro hook based on:

- **Surprising data or statistics** that create curiosity ("wait, really?")
- **Emotional moments** or mission-aligned statements that connect with viewers
- **Complete thought arcs** — don't cut mid-sentence or mid-thought
- **Strong opening line** — the first words viewers hear should grab attention

Present the recommended hook to the user with:

- Exact transcript excerpt
- Why this segment works as a hook
- Start and end timestamps (snapped to word boundaries from the `words` array)

### Step 4: Map timestamps

If transcript timestamps differ from the video timeline (common when the transcript was generated from a different edit), calculate the offset:

- Compare a recognizable moment's transcript time vs. its video time
- Document the math: `video_time = transcript_time + offset`
- Set `srt_start`/`srt_end` for the transcript range and `start`/`end` for the video range

If timestamps match (the standard case for a transcript produced by `/weftly-editing:transcribe`), `srt_start`/`srt_end` can be omitted (they default to `start`/`end`).

### Step 5: Build config & dry run

Create a JSON config file:

```json
{
  "input": "source_edit.mp4",
  "output": "source_intro_hook.mp4",
  "match": "source_edit.mp4",
  "words_json": "source_edit.words.json",
  "start": "0:11.5",
  "end": "1:14.5",
  "audio_fade_ms": 50
}
```

Run dry-run to verify:

```bash
python3 "$SCRIPT" config.json --dry-run
```

Check: timestamps, matched encoding params, segment/word counts in range.

### Step 6: Execute

After user confirmation, extract the clip:

```bash
python3 "$SCRIPT" config.json --verbose
```

Verify the output:

- Clip plays correctly with clean audio fade in/out
- `.srt` file is properly time-shifted (starts at 00:00:00)
- `.words.json` file mirrors the same range with millisecond timestamps starting at 0
- `ffprobe` output shows matching codec params to target

### Step 7: (Optional) Verify concat compatibility

Test that the clip can be spliced onto the target via stream copy:

```bash
printf "file '%s'\nfile '%s'\n" intro_hook.mp4 target.mp4 > concat_test.txt
ffmpeg -f concat -safe 0 -i concat_test.txt -c copy concat_test.mp4
```

## Config reference

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `input` | Yes | — | Source video file |
| `output` | Yes | — | Output clip file path |
| `match` | No | — | Target file to match encoding from. If omitted, uses defaults (H.264 CRF 18, AAC 192k, 29.97fps) |
| `words_json` | No | — | Source words JSON (`weftly-transcript-v2`). Preferred transcript input. |
| `srt` | No | — | Legacy SRT input. Used only if `words_json` is absent. New work should use `words_json`. |
| `start` | Yes | — | Start time in video timeline |
| `end` | Yes | — | End time in video timeline |
| `srt_start` | No | = `start` | Start time in transcript timeline (when transcript timestamps differ from video) |
| `srt_end` | No | = `end` | End time in transcript timeline |
| `audio_fade_ms` | No | `50` | Audio fade in/out duration in ms. Set to 0 to disable. |

## CLI flags

| Flag | Description |
|------|-------------|
| `--dry-run` | Preview extraction without running ffmpeg |
| `--probe-files FILE [FILE ...]` | Probe video files and print properties |
| `--verbose` | Show ffmpeg output during encoding |

## Notes

- The `match` field probes the target file and copies its encoding settings (codec, profile, FPS, pixel format, color metadata, audio settings) so the output is concat-compatible via stream copy.
- HDR sources are auto tone-mapped to SDR when the target is SDR.
- Full color range sources are auto-converted to limited range when the target uses limited.
- Uses `-ss` after `-i` for frame-accurate seeking (HEVC safe).
- Audio fades prevent click/pop artifacts at clip boundaries; 50ms default is gentle enough to be imperceptible.
- Transcript content is filtered to the `srt_start`–`srt_end` range and time-shifted to start at 00:00:00 in both `.srt` and `.words.json` outputs.
- The legacy `srt` config field is kept for backwards compat only — passing both `words_json` and `srt` will use `words_json` and warn.
