#!/usr/bin/env python3
"""Extract short intro hook clips matched to a target file for concat splicing.

Extracts a 30-60s clip from a source video, optionally matching the encoding
settings of a target file so the output can be spliced via concat demuxer
(stream copy). Also extracts and time-shifts matching transcript content from
a Weftly word-level transcript (`weftly-transcript-v2` JSON), writing both a
clipped `.words.json` and a clipped `.srt` next to the trimmed video.

Usage:
    python3 intro_clip.py config.json              # extract clip
    python3 intro_clip.py config.json --dry-run     # preview only
    python3 intro_clip.py --probe-files a.mp4 b.mp4 # probe files
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys


TRANSCRIPT_FORMAT = "weftly-transcript-v2"


def require_ffmpeg():
    """Verify ffmpeg and ffprobe are on PATH before doing any real work."""
    missing = [tool for tool in ("ffmpeg", "ffprobe") if shutil.which(tool) is None]
    if missing:
        print(
            f"Error: required tool(s) not found on PATH: {', '.join(missing)}.\n"
            "Install ffmpeg (which ships ffprobe alongside it):\n"
            "  macOS:          brew install ffmpeg\n"
            "  Debian/Ubuntu:  sudo apt install ffmpeg\n"
            "  Fedora:         sudo dnf install ffmpeg\n"
            "  Windows:        winget install ffmpeg\n"
            "Or download a build from https://ffmpeg.org/download.html",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# Time parsing
# ---------------------------------------------------------------------------

def parse_time(t):
    """Parse a time string to seconds.

    Supports: seconds (120.5), MM:SS (3:20), MM:SS.s (7:10.5),
    HH:MM:SS (1:02:30), HH:MM:SS.s (1:02:30.5).
    """
    if isinstance(t, (int, float)):
        return float(t)
    s = str(t).strip()
    parts = s.split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    raise ValueError(f"Invalid time format: {t!r}")


def fmt_time(seconds):
    """Format seconds as HH:MM:SS.s for display."""
    s = float(seconds)
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    if h > 0:
        return f"{h}:{m:02d}:{sec:05.2f}"
    return f"{m}:{sec:05.2f}"


def fmt_srt_time(seconds):
    """Format seconds as HH:MM:SS,mmm for SRT files."""
    s = float(seconds)
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    ms = int(round((s - int(s)) * 1000))
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


# ---------------------------------------------------------------------------
# Video probing (ffprobe)
# ---------------------------------------------------------------------------

def probe_file(path):
    """Probe a video file and return its properties dict."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")

    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)

    video_stream = None
    audio_stream = None
    for i, s in enumerate(data.get("streams", [])):
        if s["codec_type"] == "video" and video_stream is None:
            video_stream = s
            video_stream["_stream_index"] = i
        elif s["codec_type"] == "audio" and audio_stream is None:
            audio_stream = s
            audio_stream["_stream_index"] = i

    if video_stream is None:
        raise RuntimeError(f"No video stream found in {path}")

    fmt = data.get("format", {})

    r_frame_rate = video_stream.get("r_frame_rate", "30/1")
    fps_num, fps_den = (int(x) for x in r_frame_rate.split("/"))

    audio_bitrate = 0
    if audio_stream:
        audio_bitrate = int(audio_stream.get("bit_rate", 0))
        if audio_bitrate == 0:
            total_br = int(fmt.get("bit_rate", 0))
            if total_br > 0:
                audio_bitrate = min(192000, total_br // 10)

    props = {
        "path": path,
        "codec": video_stream.get("codec_name", "unknown"),
        "profile": video_stream.get("profile", "unknown"),
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "fps_num": fps_num,
        "fps_den": fps_den,
        "fps_str": r_frame_rate,
        "pix_fmt": video_stream.get("pix_fmt", "unknown"),
        "color_space": video_stream.get("color_space", "unknown"),
        "color_transfer": video_stream.get("color_transfer", "unknown"),
        "color_primaries": video_stream.get("color_primaries", "unknown"),
        "color_range": video_stream.get("color_range", "unknown"),
        "duration": float(fmt.get("duration", video_stream.get("duration", 0))),
        "bitrate": int(fmt.get("bit_rate", 0)),
        "video_stream_index": video_stream["_stream_index"],
        "audio_stream_index": audio_stream["_stream_index"] if audio_stream else None,
        "audio_codec": audio_stream.get("codec_name", "none") if audio_stream else "none",
        "audio_sample_rate": audio_stream.get("sample_rate", "0") if audio_stream else "0",
        "audio_channels": int(audio_stream.get("channels", 0)) if audio_stream else 0,
        "audio_bitrate": audio_bitrate,
    }
    return props


def print_probe_table(file_props):
    """Print a formatted properties table for probed files."""
    if not file_props:
        return

    labels = [
        ("Codec", lambda p: p["codec"]),
        ("Profile", lambda p: p["profile"]),
        ("Resolution", lambda p: f"{p['width']}x{p['height']}"),
        ("FPS", lambda p: p["fps_str"]),
        ("Pixel format", lambda p: p["pix_fmt"]),
        ("Color space", lambda p: p["color_space"]),
        ("Color transfer", lambda p: p["color_transfer"]),
        ("Color primaries", lambda p: p["color_primaries"]),
        ("Color range", lambda p: p["color_range"]),
        ("Stream order", lambda p: f"video={p['video_stream_index']}, audio={p['audio_stream_index']}"),
        ("Duration", lambda p: fmt_time(p["duration"])),
        ("Bitrate", lambda p: f"{p['bitrate'] / 1_000_000:.1f} Mbps" if p["bitrate"] else "unknown"),
        ("Audio", lambda p: f"{p['audio_codec']} {p['audio_sample_rate']}Hz {p['audio_channels']}ch"),
        ("Audio bitrate", lambda p: f"{p['audio_bitrate'] // 1000}k" if p["audio_bitrate"] else "unknown"),
    ]

    names = [os.path.basename(p["path"]) for p in file_props]
    max_name_len = 25
    short_names = [n if len(n) <= max_name_len else n[:max_name_len - 2] + ".." for n in names]

    prop_col_w = 16
    col_w = max(max_name_len, *(len(n) for n in short_names)) + 2

    header = f"{'Property':<{prop_col_w}}"
    for n in short_names:
        header += f" {n:<{col_w}}"
    print(header)
    print("-" * len(header))

    for label, getter in labels:
        row = f"{label:<{prop_col_w}}"
        for p in file_props:
            val = getter(p)
            row += f" {val:<{col_w}}"
        print(row)
    print()


# ---------------------------------------------------------------------------
# Transcript parsing — words JSON (canonical) + SRT fallback
# ---------------------------------------------------------------------------

SRT_TIME_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


def parse_srt_time(s):
    """Parse an SRT timestamp (HH:MM:SS,mmm) to seconds."""
    m = SRT_TIME_RE.match(s.strip())
    if not m:
        raise ValueError(f"Invalid SRT time: {s!r}")
    h, mn, sec, ms = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    return h * 3600 + mn * 60 + sec + ms / 1000.0


def parse_srt(path):
    """Parse an SRT file into a list of segment dicts.

    Each segment is {start, end, text} with start/end in **seconds**
    (matching the rest of the script's internal time representation).
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"SRT file not found: {path}")

    with open(path, encoding="utf-8-sig") as f:
        content = f.read()

    segments = []
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        try:
            int(lines[0].strip())
        except ValueError:
            continue
        time_match = re.match(
            r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})",
            lines[1].strip()
        )
        if not time_match:
            continue
        start = parse_srt_time(time_match.group(1))
        end = parse_srt_time(time_match.group(2))
        text = "\n".join(lines[2:])
        segments.append({"start": start, "end": end, "text": text})

    return segments, [], None  # (segments, words, raw) — words/raw are SRT-only nulls


def parse_words_json(path):
    """Parse a weftly-transcript-v2 JSON file.

    Source uses **milliseconds**; we convert segment/word times to **seconds**
    for the rest of the script's internal use. Returns (segments, words, raw)
    where segments are {start, end, text} in seconds, words are {word, start,
    end} in seconds, and raw is the full original document (so we can preserve
    top-level keys when writing the clipped output back).
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Words JSON file not found: {path}")

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    fmt = raw.get("format")
    if fmt != TRANSCRIPT_FORMAT:
        print(
            f"Warning: transcript format is {fmt!r} (expected {TRANSCRIPT_FORMAT!r}).",
            file=sys.stderr,
        )

    raw_segments = raw.get("segments")
    if not isinstance(raw_segments, list):
        raise ValueError("Words JSON missing 'segments' array")
    raw_words = raw.get("words", [])
    if not isinstance(raw_words, list):
        raise ValueError("Words JSON 'words' field must be an array if present")

    segments = [
        {
            "start": s["start"] / 1000.0,
            "end": s["end"] / 1000.0,
            "text": s.get("text", ""),
        }
        for s in raw_segments
    ]
    words = [
        {
            "word": w.get("word", ""),
            "start": w.get("start", 0) / 1000.0,
            "end": w.get("end", 0) / 1000.0,
        }
        for w in raw_words
    ]

    return segments, words, raw


def write_srt_from_segments(segments, path, offset):
    """Write time-shifted segments to an SRT file."""
    with open(path, "w", encoding="utf-8") as f:
        for new_idx, seg in enumerate(segments, 1):
            shifted_start = max(0.0, seg["start"] - offset)
            shifted_end = max(0.0, seg["end"] - offset)
            text = (seg.get("text") or "").strip()
            f.write(f"{new_idx}\n")
            f.write(f"{fmt_srt_time(shifted_start)} --> {fmt_srt_time(shifted_end)}\n")
            f.write(f"{text}\n\n")


def write_words_json(raw, segments, words, path, offset):
    """Write time-shifted segments + words back as a weftly-transcript-v2 JSON.

    Times are converted seconds → milliseconds; offset (seconds) is subtracted
    so the clipped transcript starts at zero.
    """
    out = dict(raw) if raw is not None else {}
    out["format"] = TRANSCRIPT_FORMAT
    out["segments"] = [
        {
            "start": int(round(max(0.0, seg["start"] - offset) * 1000)),
            "end": int(round(max(0.0, seg["end"] - offset) * 1000)),
            "text": seg.get("text", ""),
        }
        for seg in segments
    ]
    out["words"] = [
        {
            "word": w.get("word", ""),
            "start": int(round(max(0.0, w["start"] - offset) * 1000)),
            "end": int(round(max(0.0, w["end"] - offset) * 1000)),
        }
        for w in words
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_transcript(cfg):
    """Load whichever transcript format the config points at.

    Returns (segments, words, raw, source_path, source_kind) where source_kind
    is "words_json" or "srt". Returns (None, None, None, None, None) if no
    transcript is configured.
    """
    if cfg.get("words_json"):
        segments, words, raw = parse_words_json(cfg["words_json"])
        return segments, words, raw, cfg["words_json"], "words_json"
    if cfg.get("srt"):
        segments, words, raw = parse_srt(cfg["srt"])
        return segments, words, raw, cfg["srt"], "srt"
    return None, None, None, None, None


# ---------------------------------------------------------------------------
# Codec matching
# ---------------------------------------------------------------------------

def build_matched_args(match_props):
    """Build ffmpeg encoding args that match a target file's properties."""
    codec = match_props["codec"]
    if codec in ("h264", "h.264"):
        v_codec = "libx264"
    elif codec in ("hevc", "h265", "h.265"):
        v_codec = "libx265"
    else:
        v_codec = "libx264"

    profile = match_props.get("profile", "High")
    if profile and profile.lower() != "unknown":
        profile_arg = profile.lower().replace(" ", "")
        if profile_arg in ("high", "main", "baseline"):
            pass
        else:
            profile_arg = "high"
    else:
        profile_arg = "high"

    fps_str = match_props.get("fps_str", "30000/1001")
    width = match_props.get("width", 1920)
    height = match_props.get("height", 1080)
    pix_fmt = match_props.get("pix_fmt", "yuv420p")
    color_space = match_props.get("color_space", "bt709")
    color_transfer = match_props.get("color_transfer", "bt709")
    color_primaries = match_props.get("color_primaries", "bt709")
    color_range = match_props.get("color_range", "tv")

    a_codec = match_props.get("audio_codec", "aac")
    a_enc = "aac"
    if a_codec:
        a_enc = "aac"

    sample_rate = match_props.get("audio_sample_rate", "48000")
    channels = match_props.get("audio_channels", 2)
    audio_bitrate = match_props.get("audio_bitrate", 192000)
    if audio_bitrate < 64000:
        audio_bitrate = 192000

    video_args = [
        "-c:v", v_codec, "-crf", "18", "-preset", "medium",
        "-profile:v", profile_arg,
        "-s", f"{width}x{height}",
        "-r", fps_str,
        "-pix_fmt", pix_fmt,
        "-colorspace", color_space,
        "-color_trc", color_transfer,
        "-color_primaries", color_primaries,
        "-color_range", color_range,
    ]

    audio_args = [
        "-c:a", a_enc,
        "-b:a", f"{audio_bitrate // 1000}k",
        "-ar", sample_rate,
        "-ac", str(channels),
    ]

    metadata = {
        "video_codec": v_codec,
        "profile": profile_arg,
        "resolution": f"{width}x{height}",
        "fps": fps_str,
        "pix_fmt": pix_fmt,
        "color_space": color_space,
        "color_transfer": color_transfer,
        "color_primaries": color_primaries,
        "color_range": color_range,
        "audio_codec": a_enc,
        "audio_bitrate": f"{audio_bitrate // 1000}k",
        "audio_sample_rate": sample_rate,
        "audio_channels": channels,
    }

    return {"video_args": video_args, "audio_args": audio_args, "metadata": metadata}


def build_default_args():
    """Build default ffmpeg encoding args (H.264 CRF 18, AAC 192k, 29.97fps)."""
    video_args = [
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-profile:v", "high",
        "-r", "30000/1001",
        "-pix_fmt", "yuv420p",
        "-colorspace", "bt709",
        "-color_trc", "bt709",
        "-color_primaries", "bt709",
        "-color_range", "tv",
    ]
    audio_args = [
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
    ]
    metadata = {
        "video_codec": "libx264",
        "profile": "high",
        "resolution": "source",
        "fps": "30000/1001",
        "pix_fmt": "yuv420p",
        "color_space": "bt709",
        "color_transfer": "bt709",
        "color_primaries": "bt709",
        "color_range": "tv",
        "audio_codec": "aac",
        "audio_bitrate": "192k",
        "audio_sample_rate": "48000",
        "audio_channels": 2,
    }
    return {"video_args": video_args, "audio_args": audio_args, "metadata": metadata}


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(config_path):
    """Load and validate the JSON config file."""
    with open(config_path) as f:
        cfg = json.load(f)

    config_dir = os.path.dirname(os.path.abspath(config_path))

    for field in ("input", "output", "start", "end"):
        if field not in cfg:
            raise ValueError(f"Config missing required field: '{field}'")

    for key in ("input", "output", "match", "words_json", "srt"):
        if key in cfg and cfg[key] and not os.path.isabs(cfg[key]):
            cfg[key] = os.path.join(config_dir, cfg[key])

    if cfg.get("words_json") and cfg.get("srt"):
        print(
            "Note: both 'words_json' and 'srt' set in config; using 'words_json'.",
            file=sys.stderr,
        )

    cfg["_start_s"] = parse_time(cfg["start"])
    cfg["_end_s"] = parse_time(cfg["end"])
    if cfg["_end_s"] <= cfg["_start_s"]:
        raise ValueError(f"end ({cfg['end']}) must be after start ({cfg['start']})")

    cfg["_srt_start_s"] = parse_time(cfg.get("srt_start", cfg["start"]))
    cfg["_srt_end_s"] = parse_time(cfg.get("srt_end", cfg["end"]))

    cfg.setdefault("audio_fade_ms", 50)

    return cfg


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------

def cmd_probe_files(files):
    """Probe listed files and print properties table."""
    props_list = []
    for f in files:
        try:
            p = probe_file(f)
            props_list.append(p)
        except Exception as e:
            print(f"Error probing {f}: {e}", file=sys.stderr)
    if props_list:
        print_probe_table(props_list)


def cmd_extract(cfg, dry_run=False, verbose=False):
    """Extract the intro clip."""
    print("Probing input file...")
    input_props = probe_file(cfg["input"])
    print_probe_table([input_props])

    if cfg["_start_s"] >= input_props["duration"]:
        raise ValueError(
            f"start ({fmt_time(cfg['_start_s'])}) >= input duration "
            f"({fmt_time(input_props['duration'])})"
        )
    if cfg["_end_s"] > input_props["duration"] + 0.1:
        raise ValueError(
            f"end ({fmt_time(cfg['_end_s'])}) exceeds input duration "
            f"({fmt_time(input_props['duration'])})"
        )

    clip_dur = cfg["_end_s"] - cfg["_start_s"]
    print(f"Clip: {fmt_time(cfg['_start_s'])} -> {fmt_time(cfg['_end_s'])} "
          f"({clip_dur:.2f}s)")

    if cfg.get("match"):
        print(f"\nMatching encoding to: {os.path.basename(cfg['match'])}")
        match_props = probe_file(cfg["match"])
        print_probe_table([match_props])
        enc = build_matched_args(match_props)
    else:
        print("\nUsing default encoding settings (no match file)")
        enc = build_default_args()

    print("Encoding settings:")
    for k, v in enc["metadata"].items():
        print(f"  {k}: {v}")

    # Transcript handling — words JSON preferred, SRT fallback
    transcript_segments = []
    transcript_words = []
    transcript_raw = None
    transcript_source = None
    transcript_kind = None
    srt_output_path = None
    words_output_path = None

    src_segments, src_words, src_raw, src_path, src_kind = load_transcript(cfg)
    if src_segments is not None:
        print(f"\nParsing transcript ({src_kind}): {os.path.basename(src_path)}")
        print(f"  Total segments in file: {len(src_segments)}")

        srt_start = cfg["_srt_start_s"]
        srt_end = cfg["_srt_end_s"]

        for seg in src_segments:
            if seg["end"] > srt_start and seg["start"] < srt_end:
                transcript_segments.append(seg)

        if src_words:
            for w in src_words:
                if w["end"] > srt_start and w["start"] < srt_end:
                    transcript_words.append(w)

        transcript_raw = src_raw
        transcript_source = src_path
        transcript_kind = src_kind

        print(f"  Segments in range {fmt_time(srt_start)} - {fmt_time(srt_end)}: "
              f"{len(transcript_segments)}")
        if transcript_words:
            print(f"  Words in range: {len(transcript_words)}")
        if transcript_segments:
            first = transcript_segments[0]
            last = transcript_segments[-1]
            print(f"  First: [{fmt_time(first['start'])}] {first.get('text', '')[:60]}...")
            print(f"  Last:  [{fmt_time(last['start'])}] {last.get('text', '')[:60]}...")

        base, _ = os.path.splitext(cfg["output"])
        srt_output_path = base + ".srt"
        words_output_path = base + ".words.json"
        print(f"  Subtitle output: {os.path.basename(srt_output_path)}")
        if transcript_kind == "words_json":
            print(f"  Words JSON output: {os.path.basename(words_output_path)}")

    fade_ms = cfg["audio_fade_ms"]
    fade_s = fade_ms / 1000.0

    cmd = ["ffmpeg", "-y"]
    if not verbose:
        cmd.extend(["-v", "warning", "-stats"])

    cmd.extend(["-i", cfg["input"]])
    cmd.extend(["-ss", f"{cfg['_start_s']:.6f}", "-t", f"{clip_dur:.6f}"])

    vf_parts = []
    hdr_transfers = ("arib-std-b67", "smpte2084")
    if input_props["color_transfer"] in hdr_transfers:
        vf_parts.append("zscale=t=linear:npl=100")
        vf_parts.append("format=gbrpf32le")
        vf_parts.append("tonemap=hable:desat=0")
        vf_parts.append("zscale=t=bt709:m=bt709:p=bt709")
        vf_parts.append("format=yuv420p")
    elif input_props["color_range"] == "pc":
        vf_parts.append("zscale=r=limited:rangein=full")

    if vf_parts:
        cmd.extend(["-vf", ",".join(vf_parts)])

    af_parts = []
    if fade_ms > 0 and clip_dur > fade_s * 2:
        af_parts.append(f"afade=t=in:st={cfg['_start_s']:.6f}:d={fade_s:.4f}")
        af_parts.append(
            f"afade=t=out:st={cfg['_start_s'] + clip_dur - fade_s:.6f}:d={fade_s:.4f}"
        )

    if af_parts:
        cmd.extend(["-af", ",".join(af_parts)])

    cmd.extend(["-map", "0:v:0", "-map", "0:a:0"])
    cmd.extend(enc["video_args"])
    cmd.extend(enc["audio_args"])
    cmd.extend(["-movflags", "+faststart"])
    cmd.append(cfg["output"])

    cmd_str = " ".join(
        f"'{c}'" if " " in c or ";" in c or "[" in c else c
        for c in cmd
    )
    print(f"\nffmpeg command:\n{cmd_str}")

    if dry_run:
        print("\n(dry run -- not executing)")
        return

    print("\nExtracting clip...")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nffmpeg exited with code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)

    if transcript_segments and srt_output_path:
        offset = cfg["_srt_start_s"]
        write_srt_from_segments(transcript_segments, srt_output_path, offset)
        print(f"Wrote {len(transcript_segments)} segments to "
              f"{os.path.basename(srt_output_path)}")
        if transcript_kind == "words_json" and words_output_path:
            write_words_json(
                transcript_raw, transcript_segments, transcript_words,
                words_output_path, offset,
            )
            print(f"Wrote clipped words JSON to {os.path.basename(words_output_path)}")

    if os.path.isfile(cfg["output"]):
        size_mb = os.path.getsize(cfg["output"]) / (1024 * 1024)
        out_props = probe_file(cfg["output"])
        print(f"\nOutput: {cfg['output']}")
        print(f"  Size: {size_mb:.1f} MB")
        print(f"  Duration: {fmt_time(out_props['duration'])}")
        print(f"  Resolution: {out_props['width']}x{out_props['height']}")
        print(f"  Codec: {out_props['codec']} ({out_props['profile']})")
        print(f"  FPS: {out_props['fps_str']}")
        print(f"  Pixel format: {out_props['pix_fmt']}")
        print(f"  Color: {out_props['color_space']}/{out_props['color_transfer']}/{out_props['color_primaries']}")
        print(f"  Color range: {out_props['color_range']}")
        print(f"  Audio: {out_props['audio_codec']} {out_props['audio_sample_rate']}Hz {out_props['audio_channels']}ch")
    else:
        print(f"\nError: output file {cfg['output']} was not created", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract short intro hook clips matched to a target file"
    )
    parser.add_argument(
        "config", nargs="?",
        help="Path to JSON config file"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview extraction without running ffmpeg"
    )
    parser.add_argument(
        "--probe-files", nargs="+", metavar="FILE",
        help="Probe listed files and print properties table"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show ffmpeg output during encoding"
    )

    args = parser.parse_args()

    require_ffmpeg()

    if args.probe_files:
        cmd_probe_files(args.probe_files)
        return

    if not args.config:
        parser.error("config file is required (unless using --probe-files)")

    cfg = load_config(args.config)
    cmd_extract(cfg, dry_run=args.dry_run, verbose=args.verbose)


if __name__ == "__main__":
    main()
