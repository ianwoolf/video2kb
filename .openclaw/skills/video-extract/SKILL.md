---
name: video-extract
description: Extract video metadata and subtitles from YouTube or Bilibili links, with optional audio download
metadata:
  openclaw:
    requires:
      bins: [yt-dlp, ffmpeg]
      env: []
---

# video-extract

Extract video metadata and subtitles from YouTube or Bilibili links, with optional audio download.

## Usage

```bash
# Extract video info and subtitles
python3 scripts/extract_video.py --url "https://youtube.com/watch?v=xxx"

# Also download audio
python3 scripts/extract_video.py --url "https://youtube.com/watch?v=xxx" --download-audio

# Specify output directory
python3 scripts/extract_video.py --url "https://bilibili.com/video/BVxxx" --output-dir data/raw
```

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--url` | Yes | Video URL (YouTube/Bilibili) |
| `--download-audio` | No | Download audio file |
| `--output-dir` | No | Output directory (default: data/raw) |

## Output Format

JSON output to stdout:

```json
{
  "platform": "youtube",
  "url": "https://...",
  "title": "Video Title",
  "description": "Video Description",
  "duration": 600,
  "transcript": "Subtitle text...",
  "audio_path": "data/raw/xxx.mp3"
}
```

## Dependencies

- `yt-dlp` — Video metadata and audio download
- `ffmpeg` — Audio format conversion
- `youtube-transcript-api` — YouTube subtitle extraction (optional)
