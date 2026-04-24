---
description: Transcribe a source video via Weftly, then extract a 30–60s intro hook clip in one shot.
---

End-to-end pipeline: transcribe a local video via Weftly, then identify and extract a 30–60 second intro hook clip from it (with matching encoding settings to a target file for clean concat splicing). Final outputs:

- `<base>.words.json` and `<base>.srt` — the raw transcripts (per `/weftly-editing:transcribe`)
- `<intro_output>.mp4`, `<intro_output>.srt`, `<intro_output>.words.json` — the trimmed intro clip plus its time-shifted transcript (per `/weftly-editing:intro-clip`)

Input: a local video path passed as `$ARGUMENTS` (e.g., `/weftly-editing:transcribe-and-intro-clip ~/Downloads/episode.mp4`).

This is a chained orchestrator — it does not duplicate either skill's logic. The two underlying skills are the source of truth; if their behavior changes, this skill inherits the change.

## Steps

### 1. Transcribe

Execute the steps in `/weftly-editing:transcribe` against the input video. That skill handles:

- Validating the input path
- Surfacing the data retention disclosure (uploads + outputs deleted within 24h; see [weftly.ai](https://weftly.ai))
- Payment via `mppx:sign`
- Upload, polling, download
- Writing `<base>.words.json` and `<base>.srt`

If the transcribe leg fails, stop and surface the error — don't proceed to intro-clip extraction.

### 2. Identify and extract the intro hook

Once `<base>.words.json` exists, execute the steps in `/weftly-editing:intro-clip`. That skill walks through:

- Probing the input video for codec/encoding properties
- Asking the user which target file to match encoding to (so the clip can concat onto it via stream copy). For a single-file workflow, the input video itself is usually the right `match` target.
- Reading the words JSON to identify a strong 30–60s hook segment, snapping `start`/`end` to clean word boundaries
- Building a config JSON, dry-running, and finally extracting the clip

Default the `intro-clip` skill's `words_json` field to the file produced in step 1; default `match` to the input video itself unless the user names a different target.

### 3. Confirm

Print the output paths:

```
Raw transcript: <parent>/<base>.words.json
                <parent>/<base>.srt
Intro clip:     <intro_output>.mp4
                <intro_output>.srt
                <intro_output>.words.json
```

## Notes

- The intro-clip leg requires interactive judgment about where the hook actually is — don't try to silently guess. Walk the user through the recommended segment(s) before running ffmpeg.
- If `<base>.words.json` already exists alongside the input video, ask the user whether to skip step 1 and re-use the existing transcript rather than re-paying for transcription.
- The clip can be concat-spliced onto the original input video (or any other target with matching encoding) via the `concat` demuxer — see `/weftly-editing:intro-clip` for the verification command.
