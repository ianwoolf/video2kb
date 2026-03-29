---
name: whisper-transcribe
description: Convert audio files to text using Whisper ASR, with Chinese/English support and timestamps
metadata:
  openclaw:
    requires:
      bins: [python3, ffmpeg]
      env: []
---

# whisper-transcribe

Convert audio files to text using faster-whisper, with multi-language support and timestamp output.

## Usage

```bash
# Basic transcription
python3 scripts/transcribe.py --audio "data/raw/test.mp3"

# Specify language and model
python3 scripts/transcribe.py --audio "data/raw/test.mp3" --language zh --model base

# Specify output directory
python3 scripts/transcribe.py --audio "data/raw/test.mp3" --output-dir data/transcripts
```

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--audio` | Yes | Audio file path |
| `--language` | No | Language code (default: zh) |
| `--model` | No | Model size: tiny/base/small/medium/large (default: base) |
| `--output-dir` | No | Output directory (default: data/transcripts) |

## Output Format

JSON output to stdout, with `.txt` and `.srt` files saved alongside:

```json
{
  "audio_path": "data/raw/test.mp3",
  "language": "zh",
  "language_probability": 0.95,
  "duration": 1800,
  "text": "Full transcript text...",
  "segments": [
    {"start": 0.0, "end": 5.2, "text": "First sentence"},
    {"start": 5.2, "end": 10.5, "text": "Second sentence"}
  ]
}
```

## Dependencies

- `faster-whisper` — Whisper ASR engine
- `torch` — PyTorch (auto-detects CUDA/CPU)
- `ffmpeg` — Audio decoding
