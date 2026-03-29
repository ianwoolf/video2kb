---
name: text-summarize
description: Summarize long text into structured documents, extracting key points and viewpoints
metadata:
  openclaw:
    requires:
      bins: [python3]
    optional:
      env: [ZAI_API_KEY, OPENAI_API_KEY]
---

# text-summarize

Summarize long text (subtitles/transcripts) into structured documents, extracting key points and core viewpoints. Supports LLM API (Zhipu/OpenAI) for enhanced summarization; falls back to rule-based methods when no API key is available.

## Usage

```bash
# Read text from file and summarize
python3 scripts/summarize.py --input-file data/transcripts/test.txt

# Pass text directly
python3 scripts/summarize.py --text "Text content to summarize"

# Specify max length
python3 scripts/summarize.py --input-file data/transcripts/test.txt --max-length 800
```

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--text` | One of two | Text content to summarize |
| `--input-file` | One of two | Read text to summarize from a file |
| `--max-length` | No | Maximum summary length (default: 500) |
| `--output-dir` | No | Output directory (default: data/docs) |

## Output Format

JSON output to stdout:

```json
{
  "summary": "Summary content...",
  "key_points": ["Point 1", "Point 2", "Point 3"],
  "word_count": 120
}
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ZAI_API_KEY` | Zhipu AI API Key (preferred) |
| `OPENAI_API_KEY` | OpenAI API Key (fallback) |
| `LLM_MODEL` | Model name (default: glm-4.7) |

When no API key is available, the script automatically falls back to a rule-based summarization method.
