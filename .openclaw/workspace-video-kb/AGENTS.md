# Video KB Agent Responsibilities

## Available Skills

| Skill | Description | Script |
|-------|-------------|--------|
| `video-extract` | Extract metadata, subtitles, and optionally download audio from a video URL | `extract_video.py` |
| `whisper-transcribe` | Convert audio to text using Whisper ASR | `transcribe.py` |
| `text-summarize` | Generate structured summaries from long text | `summarize.py` |
| `entity-extract` | Extract named entities and relations from text | `extract_entities.py` |
| `knowledge-graph` | Store entities/relations in a graph and run queries | `graph_store.py` / `graph_query.py` |
| `report-generator` | Generate Markdown/Word analysis reports | `generate_report.py` |

## Default Configuration

- **Graph Database**: NetworkX (no external service required)
- **Language**: Chinese (zh)
- **Whisper Model**: base
- **Report Format**: Markdown
- **LLM**: Zhipu GLM-4 (if ZAI_API_KEY is available)

## Orchestration Flow

```
User inputs URL
    |
    v
[video-extract] --> Has subtitles?
    |                 |
    | No              v Yes
    v              [text-summarize]
[whisper-transcribe]   |
    |                  v
    +-------> [entity-extract]
                    |
                    v
            [knowledge-graph]
                    |
                    v
            [report-generator]
                    |
                    v
              Return results to user
```

## Data Transfer

- All Skills communicate via **JSON stdout**
- The Agent reads the JSON output of the previous step as input for the next
- Intermediate results are saved to the `data/` directory:
  - `data/raw/` — Raw audio files
  - `data/transcripts/` — Transcript files (.txt, .srt)
  - `data/docs/` — Summaries and analysis reports
  - `data/graph_state.gpickle` — NetworkX graph persistence

## Batch Processing

Supports reading a URL list from a file for batch processing. Each video runs through the full pipeline independently, and results are aggregated.
