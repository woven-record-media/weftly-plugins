#!/usr/bin/env python3
"""Remove filler words from a Weftly word-level transcript.

Reads a `weftly-transcript-v2` JSON file (per-word timestamps in milliseconds),
identifies pure-filler segments (um, uh, you know, etc.) and false starts, and
removes those where the resulting gap exceeds a threshold (~1s default).

Outputs a cleaned `<base>_cleaned.words.json` (re-indexed segments + matching
words array) and a regenerated `<base>_cleaned.srt` alongside.

Usage:
    python3 remove_fillers.py input.words.json
    python3 remove_fillers.py input.words.json --dry-run
    python3 remove_fillers.py input.words.json --threshold 1.5
    python3 remove_fillers.py input.words.json --output cleaned.words.json
"""

import argparse
import json
import os
import re
import sys


TRANSCRIPT_FORMAT = "weftly-transcript-v2"


# ---------------------------------------------------------------------------
# Time formatting (SRT output)
# ---------------------------------------------------------------------------

def fmt_srt_time(seconds):
    """Format seconds as HH:MM:SS,mmm for SRT files."""
    s = float(seconds)
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    ms = int(round((s - int(s)) * 1000))
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


# ---------------------------------------------------------------------------
# Words-JSON loading & writing
# ---------------------------------------------------------------------------

def load_words_json(path):
    """Load a weftly-transcript-v2 JSON file.

    Returns (segments, words, raw) where segments and words are lists of
    dicts with millisecond start/end fields, and raw is the original parsed
    document (so we can preserve top-level keys on write).
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Words JSON file not found: {path}")

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    fmt = raw.get("format")
    if fmt != TRANSCRIPT_FORMAT:
        print(
            f"Warning: input format is {fmt!r} (expected {TRANSCRIPT_FORMAT!r}). "
            "Proceeding, but segment/word fields may not match.",
            file=sys.stderr,
        )

    segments = raw.get("segments")
    if not isinstance(segments, list):
        raise ValueError("Input JSON missing 'segments' array")
    words = raw.get("words", [])
    if not isinstance(words, list):
        raise ValueError("Input JSON 'words' field must be an array if present")

    return segments, words, raw


def write_words_json(raw, kept_segments, kept_words, path):
    """Write the cleaned words JSON, preserving top-level metadata."""
    out = dict(raw)
    out["format"] = TRANSCRIPT_FORMAT
    out["segments"] = kept_segments
    out["words"] = kept_words
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_srt_from_segments(segments, path):
    """Regenerate an SRT file from cleaned segments (ms timestamps)."""
    with open(path, "w", encoding="utf-8") as f:
        for new_idx, seg in enumerate(segments, 1):
            start_s = seg["start"] / 1000.0
            end_s = seg["end"] / 1000.0
            text = (seg.get("text") or "").strip()
            f.write(f"{new_idx}\n")
            f.write(f"{fmt_srt_time(start_s)} --> {fmt_srt_time(end_s)}\n")
            f.write(f"{text}\n\n")


# ---------------------------------------------------------------------------
# Filler detection
# ---------------------------------------------------------------------------

# Single-word fillers (case-insensitive, allow trailing punctuation)
SINGLE_WORD_FILLERS = {
    "um", "uh", "hmm", "mm", "ah", "oh", "er", "eh",
    "umm", "uhh", "mmm", "ahh", "ohh",
}

# Short phrase fillers (case-insensitive, allow trailing punctuation)
PHRASE_FILLERS = [
    "you know",
    "i mean",
    "like",
    "so",
    "right",
    "okay",
    "ok",
]

# Trailing punctuation to strip when checking filler matches
TRAILING_PUNCT_RE = re.compile(r"[.,;:!?\-…]+$")


def is_filler(text, include_false_starts=True):
    """Check if a segment's text is a pure filler.

    Returns a string describing the filler type if it is one, or None.
    """
    cleaned = (text or "").strip()
    cleaned = re.sub(r"<[^>]+>", "", cleaned).strip()

    if not cleaned:
        return "empty"

    normalized = TRAILING_PUNCT_RE.sub("", cleaned).strip().lower()

    if not normalized:
        return "punctuation-only"

    if normalized in SINGLE_WORD_FILLERS:
        return f"filler: {normalized}"

    for phrase in PHRASE_FILLERS:
        if normalized == phrase:
            return f"filler: {phrase}"

    if include_false_starts:
        words = cleaned.split()
        if len(words) <= 3 and cleaned.rstrip().endswith(","):
            return "false start"

    return None


# ---------------------------------------------------------------------------
# Gap calculation & removal selection
# ---------------------------------------------------------------------------

def find_removable_fillers(segments, threshold_s, include_false_starts=True):
    """Identify filler segments that can be removed given a gap threshold.

    Operates on segments with millisecond start/end. The threshold is in
    seconds (matching CLI input); converted to ms internally.
    """
    threshold_ms = threshold_s * 1000.0
    removable = []

    for i, seg in enumerate(segments):
        filler_type = is_filler(seg.get("text"), include_false_starts)
        if filler_type is None:
            continue

        # Find previous meaningful segment
        prev_end = None
        for j in range(i - 1, -1, -1):
            if is_filler(segments[j].get("text"), include_false_starts) is None:
                prev_end = segments[j]["end"]
                break

        # Find next meaningful segment
        next_start = None
        for j in range(i + 1, len(segments)):
            if is_filler(segments[j].get("text"), include_false_starts) is None:
                next_start = segments[j]["start"]
                break

        if prev_end is not None and next_start is not None:
            gap_ms = next_start - prev_end
        else:
            # Filler at edges (or all-fillers) — always removable
            gap_ms = threshold_ms + 1

        if gap_ms > threshold_ms:
            removable.append((i, filler_type, gap_ms / 1000.0))

    return removable


def filter_words_by_segments(words, kept_segments):
    """Drop words that fall inside removed segments.

    A word is kept iff its [start, end] interval overlaps with the [start, end]
    of any kept segment. We use overlap rather than midpoint containment so
    boundary words near segment edges aren't accidentally dropped.
    """
    kept_ranges = [(s["start"], s["end"]) for s in kept_segments]
    if not kept_ranges:
        return []
    kept = []
    for w in words:
        ws, we = w.get("start", 0), w.get("end", 0)
        for rs, re_ in kept_ranges:
            # Intervals overlap iff ws < re_ and we > rs
            if ws < re_ and we > rs:
                kept.append(w)
                break
    return kept


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def remove_fillers(input_path, output_json_path, output_srt_path,
                   threshold_s, dry_run, include_false_starts=True):
    """Load words JSON, identify fillers, remove them, and write both outputs."""
    segments, words, raw = load_words_json(input_path)
    print(f"Parsed {len(segments)} segments and {len(words)} words from "
          f"{os.path.basename(input_path)}")

    removable = find_removable_fillers(segments, threshold_s, include_false_starts)

    if not removable:
        print("No removable filler segments found.")
        return

    total_time_saved_s = sum(
        (segments[i]["end"] - segments[i]["start"]) / 1000.0
        for i, _, _ in removable
    )

    print(f"\n{'DRY RUN: ' if dry_run else ''}Found {len(removable)} filler segments to remove:\n")
    for seg_idx, filler_type, gap_s in removable:
        seg = segments[seg_idx]
        start_s = seg["start"] / 1000.0
        end_s = seg["end"] / 1000.0
        duration = end_s - start_s
        text_preview = (seg.get("text") or "").strip()[:50]
        print(f"  #{seg_idx + 1:4d}  [{fmt_srt_time(start_s)} --> {fmt_srt_time(end_s)}] "
              f"({duration:.2f}s)  {text_preview}")
        print(f"         Type: {filler_type}  |  Gap after removal: {gap_s:.2f}s")

    print(f"\nSegments to remove: {len(removable)}")
    print(f"Time in fillers:    {total_time_saved_s:.2f}s")
    print(f"Remaining segments: {len(segments) - len(removable)}")

    if dry_run:
        print("\n(dry run -- not writing output)")
        return

    remove_indices = {i for i, _, _ in removable}
    kept_segments = [s for i, s in enumerate(segments) if i not in remove_indices]
    kept_words = filter_words_by_segments(words, kept_segments)

    write_words_json(raw, kept_segments, kept_words, output_json_path)
    print(f"\nWrote {len(kept_segments)} segments and {len(kept_words)} words to "
          f"{output_json_path}")
    write_srt_from_segments(kept_segments, output_srt_path)
    print(f"Wrote regenerated SRT to {output_srt_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def derive_output_paths(input_path, explicit_output):
    """Compute default output paths.

    For input `foo.words.json` (or `foo.json`), default outputs are
    `foo_cleaned.words.json` and `foo_cleaned.srt`.

    If --output PATH is given, use it as the words JSON output path; SRT is
    derived by stripping the JSON extension (or `.words.json`) and appending
    `.srt`.
    """
    if explicit_output:
        json_path = explicit_output
        base = json_path
        for suffix in (".words.json", ".json"):
            if base.lower().endswith(suffix):
                base = base[: -len(suffix)]
                break
        srt_path = base + ".srt"
        return json_path, srt_path

    base = input_path
    for suffix in (".words.json", ".json"):
        if base.lower().endswith(suffix):
            base = base[: -len(suffix)]
            break
    return f"{base}_cleaned.words.json", f"{base}_cleaned.srt"


def main():
    parser = argparse.ArgumentParser(
        description="Remove filler words from a Weftly word-level transcript"
    )
    parser.add_argument("input", help="Path to input words JSON file")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview removals without writing output"
    )
    parser.add_argument(
        "--threshold", type=float, default=1.0,
        help="Minimum gap (seconds) to allow filler removal (default: 1.0)"
    )
    parser.add_argument(
        "--output",
        help="Output words JSON path (default: <base>_cleaned.words.json). "
             "An SRT sibling is always written next to it."
    )
    parser.add_argument(
        "--no-false-starts", action="store_true",
        help="Disable false start detection (only remove pure filler words)"
    )

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    json_out, srt_out = derive_output_paths(args.input, args.output)

    include_false_starts = not args.no_false_starts
    remove_fillers(
        args.input, json_out, srt_out,
        args.threshold, args.dry_run,
        include_false_starts,
    )


if __name__ == "__main__":
    main()
