---
name: entity-extract
description: Extract named entities (people, organizations, locations, etc.) and their relations from text
metadata:
  openclaw:
    requires:
      bins: [python3]
    optional:
      env: [ZAI_API_KEY, OPENAI_API_KEY]
---

# entity-extract

Extract named entities and relations from text. Supports both spaCy NER and LLM-based extraction, with merged results.

## Usage

```bash
# spaCy extraction only
python3 scripts/extract_entities.py --input "Zhang San is a professor at Peking University"

# Read from file with LLM enhancement
python3 scripts/extract_entities.py --input-file data/transcripts/test.txt --use-llm

# Specify source URL
python3 scripts/extract_entities.py --input-file data/transcripts/test.txt --source-url "https://youtube.com/watch?v=xxx" --use-llm
```

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--input` | One of two | Text content to analyze |
| `--input-file` | One of two | Read text to analyze from a file |
| `--source-url` | No | Source video URL (passed to LLM context) |
| `--use-llm` | No | Use LLM-enhanced extraction (requires API Key) |

## Output Format

JSON output to stdout:

```json
{
  "entities": [
    {"text": "Zhang San", "label": "PERSON", "start": 0, "end": 2, "confidence": 0.9},
    {"text": "Peking University", "label": "ORG", "start": 4, "end": 8, "confidence": 1.0}
  ],
  "relations": [
    {"source": "Zhang San", "target": "Peking University", "relation": "WORKS_AT", "timestamp": null, "context": "", "confidence": 0.8}
  ]
}
```

## Dependencies

- `spacy` + `zh_core_web_sm` — Chinese NER (optional, skipped if not installed)
- `zhipuai` or `openai` — LLM API (optional, required for `--use-llm`)

## Related Documentation

- [Entity Schema Definition](references/entity_schema.md)
