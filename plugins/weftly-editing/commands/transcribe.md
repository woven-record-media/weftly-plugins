---
description: Transcribe a local audio/video file via Weftly. Writes <base>.words.json and <base>.srt next to the source.
---

Transcribe a local audio or video file via Weftly's MCP server. The orchestrator handles payment, upload, polling, and download — final outputs are a word-level JSON transcript (`<base>.words.json`) and an SRT (`<base>.srt`) written next to the input file.

The word-level JSON is the canonical transcript format consumed by the other `/weftly-editing:*` skills (`remove-fillers`, `intro-clip`). Tools that need plain SRT subtitles (video players, etc.) can use the `.srt` sibling.

Input: a local file path passed as `$ARGUMENTS` (e.g., `/weftly-editing:transcribe ~/Downloads/podcast.mp3`).

## Heads-up before the first paid call

This skill triggers a paid call to Weftly via your mppx wallet (configured by `/weftly-setup:weftly-setup`). Pricing: $0.50 audio, $1.00 video per file (canonical pricing is served by the Weftly MCP server at `tools/list` time).

**Data retention:** files you upload and the transcripts Weftly produces are retained for up to 24 hours and then deleted. Download anything you want to keep. See [weftly.ai](https://weftly.ai) for the privacy policy and terms of service.

## Prerequisites

- `/weftly-setup:weftly-setup` has been run on this machine, so `weftly:transcribe`, `weftly:complete_upload`, `weftly:get_job_status`, and `mppx:sign` are all available as MCP tools.
- The mppx wallet has enough USDC on Tempo mainnet to cover the call.
- `curl` is on `PATH` (used for the file upload PUT).

If `mppx:sign` or any of the `weftly:*` tools is missing, stop immediately and tell the user to run `/weftly-setup:weftly-setup --wallet <name>` and restart Claude Code. Do not attempt to work around a missing tool.

## Steps

### 1. Validate the input

- Resolve the input file path from `$ARGUMENTS`. If empty or whitespace, stop and ask: "Which file should I transcribe? Pass it as an argument, e.g. `/weftly-editing:transcribe ~/Downloads/podcast.mp3`."
- Verify the file exists with `test -f "<path>"`. If not, stop with a clear "file not found" error. Do **not** start a paid job against a missing file.
- Note the absolute path, the basename, the extension, and the parent directory. The two output files will be written into the parent directory.

### 2. Create the transcribe job

Call `weftly:transcribe` with `{ "filename": "<basename>" }` (just the filename, not the full path — Weftly infers media type from the extension).

The expected response is a `payment_required` error containing `job_id` and `payment_challenge`. Capture both.

### 3. Sign the payment

Call `mppx:sign` with the `payment_challenge` from step 2. The signed credential comes back as a string starting with `Payment ` (the full `Authorization` header value). Capture it as `payment_credential`.

### 4. Get the upload URL

Call `weftly:transcribe` again with `{ "job_id": "<job_id>", "payment_credential": "<credential>" }`. The response includes `upload_url`, `content_type`, and `expires_at` (the URL is a presigned R2 PUT and expires in ~1 hour).

### 5. Upload the file

Use a single `curl` PUT — no extra dependencies needed:

```bash
curl --fail --silent --show-error --upload-file "<absolute-path>" \
  -H "Content-Type: <content_type>" \
  "<upload_url>"
```

If `curl` exits non-zero, retry once. If it fails again, stop and surface the error verbatim — do not call `complete_upload` against a partial upload.

If the upload takes longer than the URL's `expires_at` (it shouldn't for typical files, but it's possible on very slow links for large videos), call `weftly:transcribe` again with just `{ "job_id": "<job_id>" }` (no new payment) to get a fresh upload URL, then retry the PUT.

### 6. Tell Weftly the file is ready

Call `weftly:complete_upload` with `{ "job_id": "<job_id>" }`. The response is `{ "status": "processing" }` (or the current state if it's already further along — the call is idempotent).

### 7. Poll for completion

Loop, calling `weftly:get_job_status` with `{ "job_id": "<job_id>" }` every **10 seconds**. Show the user the `progress_hint` between polls so they see motion (e.g. "Extracting audio…", "Transcribing audio…").

Status progression: `awaiting_upload → processing → extracting_audio → transcribing → completed`. Treat any of those intermediate states as normal — keep polling.

Exit conditions:

- `status == "completed"`: continue to step 8.
- `status == "failed"`: surface the response's `error_message` verbatim and stop. Weftly auto-refunds permanent failures, so the user does not need to take action on the wallet.

### 8. Download the transcripts

Call `weftly:get_job_status` twice with the inline-format option:

- `{ "job_id": "<job_id>", "format": "words" }` — returns `transcript.content` as a JSON string conforming to `weftly-transcript-v2`.
- `{ "job_id": "<job_id>", "format": "srt" }` — returns `transcript.content` as an SRT string.

Write each to disk:

- `<parent_dir>/<base>.words.json` — the words JSON content as-is (it's already a JSON string; just write it verbatim).
- `<parent_dir>/<base>.srt` — the SRT content as-is.

`<base>` is the input filename with its extension stripped (e.g. `podcast.mp3` → `podcast`).

### 9. Confirm

Print the two output paths so the user can pick them up:

```
Transcribed → <parent_dir>/<base>.words.json
              <parent_dir>/<base>.srt
```

Then mention the natural follow-ups: `/weftly-editing:remove-fillers <base>.words.json` to clean filler words, or `/weftly-editing:intro-clip` to extract a hook clip.

## Notes

- Never fabricate a `job_id` or skip a step on a hunch. Every step here is idempotent — if anything looks off, re-call `weftly:get_job_status` with the current `job_id` to see where the job actually is, and continue from that point.
- If the user interrupts mid-flow and asks to resume, take the `job_id` they give you and call `weftly:get_job_status` first to see the current state, then jump in at the matching step (skip payment if already paid; skip upload if already processing; etc.).
- Do not pass `--mcp` flags or wrap calls in shells when a direct MCP tool call works. Both `weftly:*` and `mppx:sign` are first-class MCP tools after `/weftly-setup:weftly-setup`.
