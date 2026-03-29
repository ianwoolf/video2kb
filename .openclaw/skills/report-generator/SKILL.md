---
name: report-generator
description: Generate Markdown or Word reports from video analysis results
metadata:
  openclaw:
    requires:
      bins: [python3]
---

# report-generator

Generate structured Markdown or Word reports from video analysis results (video info + analysis data).

## Usage

```bash
# Pass JSON via command line
python3 scripts/generate_report.py \
  --video-info '{"title":"Test","platform":"youtube","url":"https://...","duration":600}' \
  --analysis '{"summary":"Summary text","entities":[{"text":"Zhang San","label":"PERSON"}]}' \
  --format markdown

# Pass JSON via files
python3 scripts/generate_report.py \
  --video-info-file video_info.json \
  --analysis-file analysis.json \
  --format markdown

# Generate Word document
python3 scripts/generate_report.py \
  --video-info-file video_info.json \
  --analysis-file analysis.json \
  --format word
```

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--video-info` | One of two | Video info JSON string |
| `--video-info-file` | One of two | Video info JSON file path |
| `--analysis` | One of two | Analysis result JSON string |
| `--analysis-file` | One of two | Analysis result JSON file path |
| `--format` | No | markdown/word/both (default: markdown) |
| `--output-dir` | No | Output directory (default: data/docs) |

## Output Format

JSON output to stdout:

```json
{
  "document_path": "data/docs/Test_Video_20240101_120000.md",
  "format": "markdown"
}
```

## Report Content Structure

Generated reports include the following sections:

1. **Title** — Video title
2. **Video Info** — Source platform, link, duration, generation time
3. **Summary** — Video content summary
4. **Key Points** — Extracted key points list
5. **Transcript** — First 3000 characters of transcript
6. **Entity Recognition** — Recognized entities grouped by type
7. **Entity Relations** — Identified entity relation pairs
8. **Timeline** — Entity occurrence timeline

## Dependencies

- `python-docx` — Word document generation (optional, only needed for `--format word`)
