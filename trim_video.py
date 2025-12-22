#!/usr/bin/env python3
import subprocess
import pathlib
import re
import os
import sys

# ===== CONFIG =====
SILENCE_THRESHOLD = "-40dB"
MIN_SILENCE_DURATION = 2.0     # seconds

SILENCE_RE = re.compile(
    r"silence_start: ([0-9.]+)|silence_end: ([0-9.]+)"
)

def run(cmd):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "LC_ALL": "C"}
    )

def detect_last_silence_start(video):
    """Return silence_start timestamp (float) or None"""
    proc = run([
        "ffmpeg",
        "-i", str(video),
        "-af", f"silencedetect=n={SILENCE_THRESHOLD}:d={MIN_SILENCE_DURATION}",
        "-f", "null",
        "-"
    ])

    last_start = None
    for line in proc.stderr.splitlines():
        m = SILENCE_RE.search(line)
        if m and m.group(1):
            last_start = float(m.group(1))

    return last_start


def process_file(mkv_path, out_dir):
    """Process a single .mkv file"""
    mkv = pathlib.Path(mkv_path).resolve()
    
    print(f"Processing: {mkv.name}")

    silence_start = detect_last_silence_start(mkv)

    if silence_start is None:
        print("  No silence detected → skipped")
        return

    output = out_dir / mkv.name

    subprocess.run([
        "ffmpeg",
        "-loglevel", "error",
        "-i", str(mkv),
        "-to", f"{silence_start:.2f}",
        "-c", "copy",
        str(output)
    ])

    print(f"  Trimmed at {silence_start:.2f}s → {output}")


def process_directory(input_dir):
    """Process all .mkv files in the given directory"""
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
    
    if not mkv_files:
        print(f"No .mkv files found in '{input_path}'")
        return
    
    print(f"Found {len(mkv_files)} .mkv file(s) in '{input_path}'")
    
    for mkv in mkv_files:
        process_file(mkv, out_dir)

    print("Done.")


def process_single_file(file_path):
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
    out_dir.mkdir(exist_ok=True)
    
    process_file(file_path, out_dir)
    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Process a directory:  python trim_video.py <directory>")
        print("  Process a single file: python trim_video.py -f <file.mkv>")
        print("")
        print("Examples:")
        print("  python trim_video.py /path/to/videos")
        print("  python trim_video.py -f /path/to/video.mkv")
        sys.exit(1)
    
    if sys.argv[1] == "-f":
        if len(sys.argv) < 3:
            print("Error: Please provide a file path after -f")
            sys.exit(1)
        process_single_file(sys.argv[2])
    else:
        process_directory(sys.argv[1])