# Tool Permissions

## Shell Execution Permissions

The Agent may execute the following shell commands:

```bash
# Invoke skill scripts
python3 scripts/extract_video.py *
python3 scripts/transcribe.py *
python3 scripts/summarize.py *
python3 scripts/extract_entities.py *
python3 scripts/graph_store.py *
python3 scripts/graph_query.py *
python3 scripts/generate_report.py *
python3 scripts/run_pipeline.py *
```

## File System Permissions

### Read Access
- `data/raw/` — Raw audio files
- `data/transcripts/` — Transcript files
- `data/docs/` — Summaries and analysis results
- `data/graph_state.gpickle` — NetworkX graph data

### Write Access
- `data/raw/` — Downloaded audio files
- `data/transcripts/` — Generated transcript files
- `data/docs/` — Generated summaries and reports
- `data/graph_state.gpickle` — Graph persistence data

## Environment Variables

The Agent may access the following environment variables:

| Variable | Purpose | Required |
|----------|---------|----------|
| `ZAI_API_KEY` | Zhipu AI API Key | No |
| `OPENAI_API_KEY` | OpenAI API Key | No |
| `NEO4J_URI` | Neo4j connection URI | No |
| `NEO4J_USER` | Neo4j username | No |
| `NEO4J_PASSWORD` | Neo4j password | No |
| `WHISPER_MODEL` | Whisper model size | No |
| `LLM_MODEL` | LLM model name | No |
| `SPACY_MODEL` | spaCy model name | No |
