# cuetoflac

Split a FLAC+CUE image into individual FLAC tracks with correct lengths and embedded metadata.

## Requirements

```bash
sudo pacman -S ffmpeg python-mutagen
```

## Install

```bash
chmod +x cuetoflac.py
cp cuetoflac.py ~/.local/bin/cuetoflac
```

## Usage

```
cuetoflac [options] FILE.CUE
```

### Options

| Flag | Description |
|---|---|
| `-o`, `--output DIR` | Output directory (default: same folder as .cue) |
| `--flac FILE` | Path to FLAC source — use when the filename in the CUE sheet is wrong or garbled |
| `--encoding ENC` | CUE file encoding (default: utf-8, fallback: cp1251). Use if track names are garbled |
| `--naming TEMPLATE` | Filename template (default: `{artist} - {title}`) |
| `--no-meta` | Skip writing metadata tags |
| `--dry-run` | Preview what would happen, nothing written |
| `-v`, `--verbose` | Show ffmpeg output and timestamps |
| `-q`, `--quiet` | Suppress all output except errors |

### Naming template variables

`{n}`, `{title}`, `{artist}`, `{album}`, `{date}`, `{genre}`

### Examples

```bash
# Basic usage - FLAC and CUE in the same folder
cuetoflac album.cue

# Custom output directory
cuetoflac album.cue -o ~/Music/Album

# CUE has garbled encoding (old Windows cp1251 encoding)
cuetoflac album.cue --encoding cp1251

# FLAC filename in CUE sheet is wrong or encoded differently
cuetoflac album.cue --flac album.flac

# Both issues at once
cuetoflac album.cue -o ./Album --flac album.flac --encoding cp1251

# Custom track naming
cuetoflac album.cue --naming "{n:02d} - {title}"
cuetoflac album.cue --naming "{n:02d} - {artist} - {title}"

# Preview without writing anything
cuetoflac album.cue --dry-run -v
```

## Docker (optional)

```bash
# Build
docker build -t cuetoflac .

# Run - mount the folder containing your .cue and .flac as /data
docker run --rm -v "$(pwd)":/data cuetoflac album.cue
docker run --rm -v "$(pwd)":/data cuetoflac album.cue --flac album.flac --encoding cp1251 -o /data/Album
```

## Notes

- Output files are always overwritten if they already exist
- Encoding fallback order: UTF-8 → specified `--encoding` → cp1251
- FLAC and CUE are expected to be in the same folder unless `--flac` is used
