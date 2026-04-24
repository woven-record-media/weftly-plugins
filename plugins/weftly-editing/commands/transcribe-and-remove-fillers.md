---
description: Transcribe a local file via Weftly and remove filler words in one shot. Writes cleaned word-level JSON and SRT next to the source.
---

End-to-end pipeline: transcribe a local audio or video file via Weftly, then run filler-word removal on the resulting word-level transcript. Final outputs:

- `<base>.words.json` and `<base>.srt` — the raw transcripts (per `/weftly-editing:transcribe`)
- `<base>_cleaned.words.json` and `<base>_cleaned.srt` — the cleaned versions with filler words and false starts removed

Input: a local file path passed as `$ARGUMENTS` (e.g., `/weftly-editing:transcribe-and-remove-fillers ~/Downloads/podcast.mp3`).

This is a chained orchestrator — it does not duplicate either skill's logic. The two underlying skills are the source of truth; if their behavior changes, this skill inherits the change.

## Steps

### 1. Transcribe

Execute the steps in `/weftly-editing:transcribe` against the input file. That skill handles:

- Validating the input path
- Surfacing the data retention disclosure (uploads + outputs deleted within 24h; see [weftly.ai](https://weftly.ai))
- Payment via `mppx:sign`
- Upload to the presigned URL
- Polling and download
- Writing `<base>.words.json` and `<base>.srt`

If the transcribe leg fails (file not found, payment failure, Weftly job failed), stop. Surface the error and don't proceed to filler removal.

### 2. Remove fillers

Once `<base>.words.json` exists, execute the steps in `/weftly-editing:remove-fillers` against it. That skill:

- Locates `remove_fillers.py` inside the installed plugin
- Runs a `--dry-run` first if the user wants to preview, otherwise runs straight through
- Writes `<base>_cleaned.words.json` and `<base>_cleaned.srt`

Default to running the cleanup straight through (no dry-run), but mention the four output paths in the final summary so the user can compare raw vs cleaned if they want to.

### 3. Confirm

Print all four output paths so the user can pick up whichever they need:

```
Raw transcript:     <parent>/<base>.words.json
                    <parent>/<base>.srt
Cleaned transcript: <parent>/<base>_cleaned.words.json
                    <parent>/<base>_cleaned.srt
```

## Notes

- Both legs are idempotent in their own ways: re-running this skill against an already-transcribed file would re-pay for transcription, so don't accidentally re-run it. If `<base>.words.json` already exists alongside the input, ask the user whether to skip step 1 and just re-run filler removal against the existing transcript.
- Filler removal flags (`--threshold`, `--no-false-starts`) aren't exposed at this skill's level by default — for fine-grained control, transcribe once with `/weftly-editing:transcribe`, then run `/weftly-editing:remove-fillers` with the flags you want.
