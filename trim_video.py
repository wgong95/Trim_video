#!/usr/bin/env python3
import subprocess
import pathlib
import re
import os
import sys
import json
from datetime import datetime

# ===== CONFIG =====
SILENCE_THRESHOLD = "-35dB"
MIN_SILENCE_DURATION = 0.65    # seconds

# Global log file handle
log_file = None

SILENCE_RE = re.compile(
    r"silence_start: ([0-9.]+)|silence_end: ([0-9.]+)"
)

def log(message=""):
    """Print to console and optionally write to log file"""
    print(message)
    if log_file:
        log_file.write(message + "\n")
        log_file.flush()

def format_time(seconds):
    """Convert seconds to HH:MM:SS.mm format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:05.2f}"
    else:
        return f"{minutes:02d}:{secs:05.2f}"

def parse_time(time_str):
    """Parse time string to seconds. Supports formats: SS, MM:SS, HH:MM:SS, or decimal seconds"""
    try:
        # Try parsing as plain seconds (e.g., "123.45")
        return float(time_str)
    except ValueError:
        pass
    
    # Try parsing as HH:MM:SS or MM:SS
    parts = time_str.split(':')
    try:
        if len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        pass
    
    raise ValueError(f"Invalid time format: {time_str}. Use SS, MM:SS, or HH:MM:SS")

def run(cmd):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "LC_ALL": "C"}
    )

def detect_all_silences(video):
    """Return list of all silence periods as [(start, end, duration), ...]"""
    proc = run([
        "ffmpeg",
        "-i", str(video),
        "-af", f"silencedetect=n={SILENCE_THRESHOLD}:d={MIN_SILENCE_DURATION}",
        "-f", "null",
        "-"
    ])

    silences = []
    current_start = None
    
    for line in proc.stderr.splitlines():
        m = SILENCE_RE.search(line)
        if m:
            if m.group(1):  # silence_start
                current_start = float(m.group(1))
            elif m.group(2) and current_start is not None:  # silence_end
                end = float(m.group(2))
                duration = end - current_start
                silences.append((current_start, end, duration))
                current_start = None
    
    # Handle case where silence extends to end of file (no silence_end)
    if current_start is not None:
        silences.append((current_start, None, None))
    
    return silences

def get_cache_path(video_path):
    """Get the cache file path for a video"""
    video = pathlib.Path(video_path).resolve()
    return video.parent / f".{video.stem}_silence_cache.json"

def save_silences_to_cache(video_path, silences):
    """Save silence detection results to cache file"""
    cache_path = get_cache_path(video_path)
    cache_data = {
        "video": str(video_path),
        "threshold": SILENCE_THRESHOLD,
        "min_duration": MIN_SILENCE_DURATION,
        "timestamp": datetime.now().isoformat(),
        "silences": silences
    }
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2)
    return cache_path

def load_silences_from_cache(video_path):
    """Load silence detection results from cache file if valid"""
    cache_path = get_cache_path(video_path)
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
        
        # Check if cache matches current settings
        if (cache_data.get("threshold") == SILENCE_THRESHOLD and
            cache_data.get("min_duration") == MIN_SILENCE_DURATION):
            # Convert lists back to tuples
            silences = [tuple(s) for s in cache_data.get("silences", [])]
            return silences
    except (json.JSONDecodeError, KeyError):
        pass
    
    return None

def get_silences_with_cache(video_path, use_cache=True):
    """Get silences, using cache if available and valid"""
    video = pathlib.Path(video_path).resolve()
    
    if use_cache:
        cached = load_silences_from_cache(video)
        if cached is not None:
            log(f"  Using cached silence data")
            return cached
    
    log(f"  Detecting silences (threshold={SILENCE_THRESHOLD}, min_duration={MIN_SILENCE_DURATION}s)...")
    silences = detect_all_silences(video)
    
    # Save to cache for future use
    if silences:
        save_silences_to_cache(video, silences)
    
    return silences

def detect_last_silence_start(video):
    """Return silence_start timestamp (float) or None"""
    silences = detect_all_silences(video)
    if silences:
        return silences[-1][0]
    return None

def print_silence_report(video, silences):
    """Print a detailed report of all detected silence periods"""
    log(f"\n{'='*60}")
    log(f"Silence Report: {video.name}")
    log(f"{'='*60}")
    
    if not silences:
        log("  No silence detected")
        return
    
    log(f"\n  Found {len(silences)} silence period(s):\n")
    log(f"  {'#':<4} {'Start':<12} {'End':<12} {'Duration':<10}")
    log(f"  {'-'*4} {'-'*12} {'-'*12} {'-'*10}")
    
    for i, (start, end, duration) in enumerate(silences, 1):
        start_str = format_time(start)
        if end is not None:
            end_str = format_time(end)
            dur_str = f"{duration:.2f}s"
        else:
            end_str = "EOF"
            dur_str = "→ EOF"
        log(f"  {i:<4} {start_str:<12} {end_str:<12} {dur_str:<10}")
    
    log(f"\n  Last silence starts at: {format_time(silences[-1][0])}")
    log(f"  Video will be trimmed at this point.\n")


def trim_at_time(mkv_path, cut_time, out_dir):
    """Trim a video at a specific time point"""
    mkv = pathlib.Path(mkv_path).resolve()
    output = out_dir / mkv.name
    
    # Skip if output already exists
    if output.exists():
        log(f"Skipping: {mkv.name} (already exists in trimmed folder)")
        return
    
    log(f"Processing: {mkv.name}")
    log(f"  Cutting at: {format_time(cut_time)}")
    
    subprocess.run([
        "ffmpeg",
        "-loglevel", "error",
        "-i", str(mkv),
        "-to", f"{cut_time:.2f}",
        "-c", "copy",
        str(output)
    ])
    
    log(f"  ✓ Trimmed at {format_time(cut_time)} → {output}")


def split_by_silence(mkv_path, out_dir, preview_only=False):
    """Split a video into multiple parts based on silence gaps"""
    mkv = pathlib.Path(mkv_path).resolve()
    base_name = mkv.stem
    ext = mkv.suffix
    
    log(f"Processing: {mkv.name}")
    
    silences = get_silences_with_cache(mkv)
    
    if not silences:
        log("  No silence detected → cannot split")
        return
    
    # Show silence report
    print_silence_report(mkv, silences)
    
    # Calculate split points (use middle of each silence gap)
    split_points = []
    for start, end, duration in silences:
        if end is not None:
            # Use the middle of the silence as split point
            mid_point = (start + end) / 2
            split_points.append(mid_point)
        else:
            # Silence extends to EOF, use start as final cut
            split_points.append(start)
    
    # Create segments: from 0 to first split, between splits, last split to end
    segments = []
    prev_point = 0
    for i, point in enumerate(split_points):
        segments.append((prev_point, point))
        prev_point = point
    
    # Determine number of digits needed for naming
    num_digits = max(2, len(str(len(segments))))
    
    log(f"\n  Will create {len(segments)} segment(s):")
    for i, (start, end) in enumerate(segments, 1):
        output_name = f"{base_name}_{i:0{num_digits}d}{ext}"
        log(f"    {i:0{num_digits}d}: {format_time(start)} → {format_time(end)}  [{output_name}]")
    
    if preview_only:
        log("\n  Preview mode - no files created")
        return
    
    log(f"\n  Creating segments...")
    
    for i, (start, end) in enumerate(segments, 1):
        output_name = f"{base_name}_{i:0{num_digits}d}{ext}"
        output = out_dir / output_name
        
        # Skip if output already exists
        if output.exists():
            log(f"    Skipping {output_name} (already exists)")
            continue
        
        subprocess.run([
            "ffmpeg",
            "-loglevel", "error",
            "-i", str(mkv),
            "-ss", f"{start:.2f}",
            "-to", f"{end:.2f}",
            "-c", "copy",
            str(output)
        ])
        
        log(f"    ✓ Created {output_name}")
    
    log(f"\n  ✓ Split complete: {len(segments)} segments created")


def process_file(mkv_path, out_dir, preview_only=False):
    """Process a single .mkv file"""
    mkv = pathlib.Path(mkv_path).resolve()
    output = out_dir / mkv.name
    
    # Skip if output already exists (unless preview mode)
    if not preview_only and output.exists():
        log(f"Skipping: {mkv.name} (already exists in trimmed folder)")
        return
    
    log(f"Processing: {mkv.name}")

    silences = get_silences_with_cache(mkv)
    
    if not silences:
        log("  No silence detected → skipped")
        return

    # Always show silence report
    print_silence_report(mkv, silences)
    
    if preview_only:
        return
    
    silence_start = silences[-1][0]

    subprocess.run([
        "ffmpeg",
        "-loglevel", "error",
        "-i", str(mkv),
        "-to", f"{silence_start:.2f}",
        "-c", "copy",
        str(output)
    ])

    log(f"  ✓ Trimmed at {format_time(silence_start)} → {output}")


def process_directory(input_dir, preview_only=False):
    """Process all .mkv files in the given directory"""
    global log_file
    input_path = pathlib.Path(input_dir).resolve()
    
    if not input_path.exists():
        print(f"Error: Directory '{input_path}' does not exist")
        return
    
    if not input_path.is_dir():
        print(f"Error: '{input_path}' is not a directory")
        return
    
    # Create trimmed subdirectory in the input directory
    out_dir = input_path / "trimmed"
    if not preview_only:
        out_dir.mkdir(exist_ok=True)
    
    mkv_files = list(input_path.glob("*.mkv"))
    mkv_files.sort()  # Sort files for consistent ordering
    
    if not mkv_files:
        print(f"No .mkv files found in '{input_path}'")
        return
    
    # Create log file for batch processing
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = input_path / f"trim_video_{timestamp}.log"
    log_file = open(log_path, "w", encoding="utf-8")
    
    log(f"Trim Video Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Directory: {input_path}")
    log(f"Found {len(mkv_files)} .mkv file(s)")
    if preview_only:
        log("Mode: Preview only (no files will be modified)\n")
    else:
        log(f"Output directory: {out_dir}\n")
    
    for mkv in mkv_files:
        process_file(mkv, out_dir, preview_only)

    log("\n" + "="*60)
    log("Done.")
    log(f"Log saved to: {log_path}")
    
    log_file.close()
    log_file = None
    
    print(f"\n📄 Log saved to: {log_path}")


def process_single_file(file_path, preview_only=False):
    """Process a single .mkv file"""
    file_path = pathlib.Path(file_path).resolve()
    
    if not file_path.exists():
        print(f"Error: File '{file_path}' does not exist")
        return
    
    if not file_path.is_file():
        print(f"Error: '{file_path}' is not a file")
        return
    
    if file_path.suffix.lower() != '.mkv':
        print(f"Error: '{file_path}' is not a .mkv file")
        return
    
    # Create trimmed subdirectory in the file's parent directory
    out_dir = file_path.parent / "trimmed"
    if not preview_only:
        out_dir.mkdir(exist_ok=True)
    
    process_file(file_path, out_dir, preview_only)
    print("Done.")


def trim_directory_at_time(input_dir, cut_time):
    """Trim all .mkv files in a directory at a specific time point"""
    global log_file
    input_path = pathlib.Path(input_dir).resolve()
    
    if not input_path.exists():
        print(f"Error: Directory '{input_path}' does not exist")
        return
    
    if not input_path.is_dir():
        print(f"Error: '{input_path}' is not a directory")
        return
    
    # Create trimmed subdirectory in the input directory
    out_dir = input_path / "trimmed"
    out_dir.mkdir(exist_ok=True)
    
    mkv_files = list(input_path.glob("*.mkv"))
    mkv_files.sort()  # Sort files for consistent ordering
    
    if not mkv_files:
        print(f"No .mkv files found in '{input_path}'")
        return
    
    # Create log file for batch processing
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = input_path / f"trim_video_{timestamp}.log"
    log_file = open(log_path, "w", encoding="utf-8")
    
    log(f"Trim Video Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Directory: {input_path}")
    log(f"Found {len(mkv_files)} .mkv file(s)")
    log(f"Cut time: {format_time(cut_time)}")
    log(f"Output directory: {out_dir}\n")
    
    for mkv in mkv_files:
        trim_at_time(mkv, cut_time, out_dir)

    log("\n" + "="*60)
    log("Done.")
    log(f"Log saved to: {log_path}")
    
    log_file.close()
    log_file = None
    
    print(f"\n📄 Log saved to: {log_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Process a directory:    python trim_video.py <directory>")
        print("  Process a single file:  python trim_video.py -f <file.mkv>")
        print("  Preview only (no trim): python trim_video.py -p <directory>")
        print("                          python trim_video.py -p -f <file.mkv>")
        print("  Manual cut at time:     python trim_video.py -t <time> -f <file.mkv>")
        print("                          python trim_video.py -t <time> <directory>")
        print("  Split by silence:       python trim_video.py -s -f <file.mkv>")
        print("")
        print("Options:")
        print("  -f         Process a single file instead of a directory")
        print("  -p         Preview mode: show silence report without trimming")
        print("  -t <time>  Manual cut: trim video at specified time (keeps 0 to time)")
        print("             Time formats: 123.45 (seconds), 2:03 (MM:SS), 1:02:03 (HH:MM:SS)")
        print("             Can be used with a single file (-f) or a directory")
        print("  -s         Split mode: split video into segments at silence gaps")
        print("             Output files named as: filename_01.mkv, filename_02.mkv, ...")
        print("")
        print("Examples:")
        print("  python trim_video.py /path/to/videos")
        print("  python trim_video.py -f /path/to/video.mkv")
        print("  python trim_video.py -p /path/to/videos          # Preview only")
        print("  python trim_video.py -p -f /path/to/video.mkv    # Preview single file")
        print("  python trim_video.py -t 8717.17 -f /path/to/video.mkv   # Cut single file")
        print("  python trim_video.py -t 2:25:17 -f /path/to/video.mkv   # Cut at 2h25m17s")
        print("  python trim_video.py -t 10:30 /path/to/videos    # Cut all files at 10:30")
        print("  python trim_video.py -s -f /path/to/video.mkv    # Split by silence")
        print("  python trim_video.py -s -p -f /path/to/video.mkv # Preview split points")
        sys.exit(1)
    
    # Parse arguments
    preview_only = "-p" in sys.argv
    single_file = "-f" in sys.argv
    split_mode = "-s" in sys.argv
    
    # Check for manual cut time (-t)
    cut_time = None
    if "-t" in sys.argv:
        t_index = sys.argv.index("-t")
        if t_index + 1 < len(sys.argv):
            try:
                cut_time = parse_time(sys.argv[t_index + 1])
            except ValueError as e:
                print(f"Error: {e}")
                sys.exit(1)
        else:
            print("Error: Please provide a time value after -t")
            sys.exit(1)
    
    # Get the path (last argument that doesn't start with -)
    path_arg = None
    args_to_skip = set()
    if "-t" in sys.argv:
        t_index = sys.argv.index("-t")
        args_to_skip.add(t_index)
        args_to_skip.add(t_index + 1)
    
    for i, arg in enumerate(sys.argv[1:], 1):
        if i not in args_to_skip and not arg.startswith("-"):
            path_arg = arg
    
    if path_arg is None:
        print("Error: Please provide a path")
        sys.exit(1)
    
    # Manual cut mode
    if cut_time is not None:
        if single_file:
            # Single file mode
            file_path = pathlib.Path(path_arg).resolve()
            if not file_path.exists():
                print(f"Error: File '{file_path}' does not exist")
                sys.exit(1)
            
            out_dir = file_path.parent / "trimmed"
            out_dir.mkdir(exist_ok=True)
            
            trim_at_time(file_path, cut_time, out_dir)
            print("Done.")
        else:
            # Directory mode - trim all files at the same time
            trim_directory_at_time(path_arg, cut_time)
    # Split mode
    elif split_mode:
        if not single_file:
            print("Error: Split mode (-s) requires a single file (-f)")
            sys.exit(1)
        
        file_path = pathlib.Path(path_arg).resolve()
        if not file_path.exists():
            print(f"Error: File '{file_path}' does not exist")
            sys.exit(1)
        
        out_dir = file_path.parent / "trimmed"
        if not preview_only:
            out_dir.mkdir(exist_ok=True)
        
        split_by_silence(file_path, out_dir, preview_only)
        print("Done.")
    elif single_file:
        process_single_file(path_arg, preview_only)
    else:
        process_directory(path_arg, preview_only)