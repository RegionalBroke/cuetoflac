#!/usr/bin/env python3
"""
cuetoflac — split a FLAC+CUE image into individual FLAC tracks
Usage: cuetoflac [options] <file.cue>
"""

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from mutagen.flac import FLAC


# ─── CUE PARSER ──────────────────────────────────────────────────────────────

@dataclass
class Track:
    number: int
    title: str = ""
    artist: str = ""
    index: str = "00:00:00"  # MM:SS:FF (frames)


@dataclass
class CueSheet:
    file: str = ""
    album: str = ""
    album_artist: str = ""
    date: str = ""
    genre: str = ""
    tracks: list = field(default_factory=list)


def parse_cue(cue_path: Path, encoding: str | None = None) -> CueSheet:
    """Parse a .cue file into a CueSheet object."""
    sheet = CueSheet()
    current_track = None

    # Detect encoding: try UTF-8, then --encoding override or cp1251, then latin-1
    raw = cue_path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        enc = encoding or "cp1251"
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            text = raw.decode("latin-1")

    for line in text.splitlines():
        line = line.strip()

        m = re.match(r'^FILE\s+"?(.+?)"?\s+\w+$', line)
        if m:
            sheet.file = m.group(1)
            continue

        m = re.match(r'^TITLE\s+"?(.+?)"?$', line)
        if m:
            if current_track is None:
                sheet.album = m.group(1)
            else:
                current_track.title = m.group(1)
            continue

        m = re.match(r'^PERFORMER\s+"?(.+?)"?$', line)
        if m:
            if current_track is None:
                sheet.album_artist = m.group(1)
            else:
                current_track.artist = m.group(1)
            continue

        m = re.match(r'^REM\s+DATE\s+(.+)$', line)
        if m:
            sheet.date = m.group(1).strip('"')
            continue

        m = re.match(r'^REM\s+GENRE\s+(.+)$', line)
        if m:
            sheet.genre = m.group(1).strip('"')
            continue

        m = re.match(r'^TRACK\s+(\d+)\s+AUDIO$', line)
        if m:
            if current_track is not None:
                sheet.tracks.append(current_track)
            current_track = Track(number=int(m.group(1)))
            # Inherit album artist if track has none yet
            current_track.artist = sheet.album_artist
            continue

        m = re.match(r'^INDEX\s+01\s+(\d{2}:\d{2}:\d{2})$', line)
        if m and current_track is not None:
            current_track.index = m.group(1)
            continue

    if current_track is not None:
        sheet.tracks.append(current_track)

    return sheet


# ─── TIME UTILS ──────────────────────────────────────────────────────────────

def cue_time_to_seconds(timecode: str) -> float:
    """Convert CUE MM:SS:FF timecode to seconds (75 frames/sec)."""
    parts = timecode.split(":")
    mm, ss, ff = int(parts[0]), int(parts[1]), int(parts[2])
    return mm * 60 + ss + ff / 75.0


def seconds_to_ffmpeg(s: float) -> str:
    """Format seconds as ffmpeg-compatible timestamp."""
    return f"{s:.6f}"


# ─── NAMING ──────────────────────────────────────────────────────────────────

def safe_filename(name: str) -> str:
    """Strip characters that are problematic in filenames."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip()


def build_filename(template: str, track: Track, sheet: CueSheet) -> str:
    """Expand naming template to a filename (without extension)."""
    artist = track.artist or sheet.album_artist or "Unknown Artist"
    title = track.title or f"Track {track.number:02d}"
    result = template.format(
        n=track.number,
        title=title,
        artist=artist,
        album=sheet.album or "Unknown Album",
        date=sheet.date or "",
        genre=sheet.genre or "",
    )
    return safe_filename(result)


# ─── FFMPEG SPLIT ────────────────────────────────────────────────────────────

def split_track(
    flac_source: Path,
    start: float,
    end: float | None,
    output_path: Path,
    verbose: bool,
) -> bool:
    """Use ffmpeg to cut a single track from the source FLAC."""
    cmd = ["ffmpeg", "-y", "-i", str(flac_source), "-ss", seconds_to_ffmpeg(start)]
    if end is not None:
        cmd += ["-to", seconds_to_ffmpeg(end)]
    cmd += ["-c:a", "flac", str(output_path)]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE if not verbose else None,
    )
    return result.returncode == 0


# ─── METADATA ────────────────────────────────────────────────────────────────

def write_metadata(path: Path, track: Track, sheet: CueSheet):
    """Embed Vorbis comment metadata into the output FLAC."""
    audio = FLAC(path)
    audio.clear()

    artist = track.artist or sheet.album_artist or ""
    title = track.title or f"Track {track.number:02d}"

    audio["title"] = title
    audio["tracknumber"] = str(track.number)
    if artist:
        audio["artist"] = artist
    if sheet.album:
        audio["album"] = sheet.album
    if sheet.album_artist and sheet.album_artist != artist:
        audio["albumartist"] = sheet.album_artist
    if sheet.date:
        audio["date"] = sheet.date
    if sheet.genre:
        audio["genre"] = sheet.genre

    audio.save()


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="cuetoflac",
        description="Split a FLAC+CUE image into individual FLAC tracks.",
    )
    parser.add_argument("cue", metavar="FILE.CUE", help="path to the .cue file")
    parser.add_argument(
        "-o", "--output", metavar="DIR",
        help="output directory (default: same as .cue file)",
    )
    parser.add_argument(
        "--encoding", metavar="ENC",
        help="CUE file encoding (default: utf-8, fallback: cp1251). "
             "Use if track names are garbled, e.g. --encoding cp1251",
    )
    parser.add_argument(
        "--flac", metavar="FILE",
        help="path to the FLAC source (overrides the FILE entry in the CUE sheet)",
    )
    parser.add_argument(
        "--naming", metavar="TEMPLATE",
        default="{artist} - {title}",
        help='filename template (default: "{artist} - {title}")\n'
             "available: {n}, {title}, {artist}, {album}, {date}, {genre}",
    )
    parser.add_argument(
        "--no-meta", action="store_true",
        help="skip writing metadata tags",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="show what would be done without actually doing it",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="show ffmpeg output",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="suppress all output except errors",
    )

    args = parser.parse_args()

    cue_path = Path(args.cue).resolve()
    if not cue_path.exists():
        print(f"error: CUE file not found: {cue_path}", file=sys.stderr)
        sys.exit(1)

    # Check ffmpeg
    if subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode != 0:
        print("error: ffmpeg not found. Install it with: sudo pacman -S ffmpeg", file=sys.stderr)
        sys.exit(1)

    sheet = parse_cue(cue_path, encoding=args.encoding)

    if not sheet.file:
        print("error: no FILE entry found in CUE sheet", file=sys.stderr)
        sys.exit(1)

    # Resolve the FLAC source (--flac overrides the FILE entry in the CUE sheet)
    if args.flac:
        flac_source = Path(args.flac).resolve()
    else:
        flac_source = cue_path.parent / sheet.file
    if not flac_source.exists():
        print(f"error: FLAC source not found: {flac_source}", file=sys.stderr)
        sys.exit(1)

    # Output directory
    out_dir = Path(args.output).resolve() if args.output else cue_path.parent
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    if not args.quiet:
        print(f"  source : {flac_source.name}")
        print(f"  album  : {sheet.album or '(unknown)'}")
        print(f"  artist : {sheet.album_artist or '(unknown)'}")
        print(f"  tracks : {len(sheet.tracks)}")
        print(f"  output : {out_dir}")
        print()

    # Split each track
    errors = 0
    for i, track in enumerate(sheet.tracks):
        start = cue_time_to_seconds(track.index)
        end = (
            cue_time_to_seconds(sheet.tracks[i + 1].index)
            if i + 1 < len(sheet.tracks)
            else None
        )

        filename = build_filename(args.naming, track, sheet) + ".flac"
        out_path = out_dir / filename

        artist = track.artist or sheet.album_artist or "?"
        title = track.title or f"Track {track.number:02d}"

        if not args.quiet:
            end_display = f"{end:.2f}s" if end else "end"
            print(f"  [{track.number:02d}] {artist} — {title}")
            if args.verbose:
                print(f"        {start:.2f}s → {end_display}  →  {filename}")

        if args.dry_run:
            continue

        ok = split_track(flac_source, start, end, out_path, args.verbose)
        if not ok:
            print(f"  error: ffmpeg failed on track {track.number}", file=sys.stderr)
            errors += 1
            continue

        if not args.no_meta:
            write_metadata(out_path, track, sheet)

    if args.dry_run and not args.quiet:
        print("\n(dry run — nothing written)")
    elif not args.quiet:
        status = "done" if errors == 0 else f"done with {errors} error(s)"
        print(f"\n  {status}.")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
