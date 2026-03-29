# Video Analysis Scripts

This directory contains standalone CLI scripts for video content analysis and knowledge graph construction. Each script can be run independently or orchestrated by `run_pipeline.py`.

## Scripts Overview

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `extract_video.py` | Extract video info and subtitles/audio | Video URL | JSON with video info, transcript, audio path |
| `transcribe.py` | Speech recognition using Whisper | Audio file path | JSON with transcribed text |
| `summarize.py` | Generate text summary | Text input/file | JSON with summary and key points |
| `extract_entities.py` | Extract named entities and relations | Text input/file | JSON with entities and relations |
| `graph_store.py` | Store data to knowledge graph | Video info, entities, relations | JSON with storage results |
| `graph_query.py` | Query the knowledge graph | Entity name | JSON with query results |
| `generate_report.py` | Generate Markdown/Word report | Video info, analysis data | JSON with document path |
| `run_pipeline.py` | Orchestrate full pipeline | Video URL or batch file | Complete analysis results |
| `quick_test.py` | Test with mock data | None | Test output |

## Quick Start

### Run Full Pipeline

```bash
# Analyze a single video
python3 scripts/run_pipeline.py --url "https://www.youtube.com/watch?v=xxx"

# Batch processing
python3 scripts/run_pipeline.py --batch urls.txt

# Use Neo4j instead of NetworkX
python3 scripts/run_pipeline.py --url "..." --graph neo4j
```

### Run Individual Scripts

```bash
# Extract video info
python3 scripts/extract_video.py --url "https://youtube.com/watch?v=xxx"

# Transcribe audio
python3 scripts/transcribe.py --audio data/raw/audio.mp3

# Summarize text
python3 scripts/summarize.py --input "text to summarize"

# Extract entities
python3 scripts/extract_entities.py --input-file transcript.txt

# Query knowledge graph
python3 scripts/graph_query.py --entity "entity_name"
```

## Common Options

| Option | Description |
|--------|-------------|
| `--url` | Video URL (YouTube/Bilibili) |
| `--input` | Text input (as string) |
| `--input-file` | Text input file path |
| `--output-dir` | Output directory (default varies by script) |
| `--format` | Output format (markdown/word/both) |
| `--use-llm` | Enable LLM-enhanced extraction |
| `--graph` | Graph database type (networkx/neo4j) |

## Dependencies

All scripts require Python 3.8+. Install dependencies:

```bash
pip install -r requirements.txt
```

### System Requirements

- **FFmpeg** - Required for audio extraction and Whisper ASR
  ```bash
  brew install ffmpeg  # macOS
  sudo apt install ffmpeg  # Ubuntu/Debian
  ```

- **Neo4j** (optional) - For Neo4j graph database mode
  ```bash
  docker-compose up -d  # Start Neo4j container
  ```

## Environment Variables

Create a `.env` file (see `.env.example` for reference):

```bash
# Required for LLM features
OPENAI_API_KEY=sk-xxx
ZAI_API_KEY=your_key_here

# Neo4j configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Model configuration
WHISPER_MODEL=base  # tiny/base/small/medium/large
LLM_PROVIDER=zai   # zai/openai
GRAPH_DB_TYPE=networkx  # networkx/neo4j
```

## Data Flow

```
Video URL
    ↓
extract_video.py → video_info.json + (audio.mp3 or transcript.txt)
    ↓
transcribe.py (if no subtitles) → transcript.txt
    ↓
summarize.py → summary.json
    ↓
extract_entities.py → entities.json + relations.json
    ↓
graph_store.py → knowledge graph (Neo4j/NetworkX)
    ↓
generate_report.py → report.md
```

## Output Locations

| Type | Default Directory |
|------|-------------------|
| Raw audio/video | `data/raw/` |
| Transcripts | `data/transcripts/` |
| Generated docs | `data/docs/` |
| Graph data | Neo4j database or memory (NetworkX) |

## Examples

See [USAGE.md](../USAGE.md) for detailed examples and [README.md](../README.md) for project overview.
