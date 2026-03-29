# Video Content Analysis Demo - Technical Solution and Implementation

## Project Goal

Extract content from YouTube/Bilibili videos, perform entity recognition, and build a Knowledge Graph (Knowledge Base), achieving:
1. Video subtitle/audio extraction
2. Content summarization
3. Entity extraction and relationship mapping
4. Knowledge graph storage and retrieval

---

## Technology Stack Analysis

### 1. Video Content Extraction

| Platform | Recommended Tool | Description |
|------|----------|------|
| **YouTube** | `yt-dlp` + `youtube-transcript-api` | Extract subtitles, audio, metadata |
| **Bilibili** | `bilibili-api` + `yt-dlp` | Extract subtitles, video information |

**Core Libraries:**
```python
# YouTube
yt-dlp                    # Download video/audio/subtitles
youtube-transcript-api    # Fetch subtitle text

# Bilibili
bilibili-api              # Bilibili API wrapper
yt-dlp                    # General-purpose video downloader
```

**System Dependencies:**
- **FFmpeg**: The core tool for audio/video processing. `yt-dlp` depends on it to extract audio streams from video files; Whisper ASR also depends on it for audio format conversion. Without FFmpeg, neither audio extraction nor speech recognition can run.

---

### 2. Speech Recognition (ASR)

If the video has no subtitles, text needs to be extracted from the audio:

| Tool | Advantage | Use Case |
|------|------|----------|
| **Whisper** | High accuracy, open-source, multilingual | Local deployment |
| **Faster-Whisper** | Fast speed | Large-scale batch processing |
| **Azure/Google/Tencent ASR** | Cloud service | Production environments |

**Recommended:**
```python
openai-whisper          # OpenAI official model
faster-whisper          # Optimized inference version
```

**Model Download:**
- **Hugging Face Hub**: Model weight files for Whisper and similar models are hosted on Hugging Face. On first run, `faster-whisper` automatically downloads models to the local cache (`~/.cache/huggingface/`) via `huggingface_hub`. Access to Hugging Face from within mainland China can be unstable, so you need to set the mirror source `HF_ENDPOINT=https://hf-mirror.com` to accelerate downloads.

---

### 3. MCP (Model Context Protocol)

MCP is a protocol proposed by Anthropic for connecting AI models with external tools/data sources.

**Existing MCP Tools:**
- `@modelcontextprotocol/server-filesystem` - File system access
- `@modelcontextprotocol/server-brave-search` - Web search
- `@modelcontextprotocol/server-git` - Git operations
- Custom MCP Server - Wrap your video analysis logic

**Why MCP?**
- Standardized protocol, easy to integrate into MCP-supported platforms like Claude
- Lightweight tool invocation
- Highly extensible

---

### 4. GraphRAG (Graph-based Retrieval Augmented Generation)

GraphRAG combines knowledge graphs with vector retrieval to improve RAG effectiveness.

**Core Components:**
1. **Entity Extraction**
   - LLM identifies entities from text (person names, locations, concepts, etc.)
   - Extracts relationships between entities

2. **Knowledge Graph Construction**
   - Graph database storage (Neo4j / Memgraph / NetworkX)
   - Nodes = Entities, Edges = Relationships

3. **Vector Embedding**
   - Vectorize entities/documents
   - Support similarity retrieval

4. **Retrieval Augmentation**
   - At query time: entity -> graph -> related documents
   - Combine vector retrieval with graph traversal

**Recommended Technology Stack:**
```python
# Knowledge Graph
neo4j                    # Production-grade graph database
memgraph                 # Neo4j-compatible high-performance version
networkx                 # Lightweight, suitable for demos

# Vector Retrieval
chromadb / qdrant        # Vector databases
sentence-transformers    # Chinese embedding models

# Entity Extraction
spaCy / LlamaIndex       # NLP entity recognition
LLM (GLM-4, Claude)      # LLM-based extraction
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       User Request                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │    MCP Server         │
         │  (Tool/Data Wrapper)  │
         └───────────┬───────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│ Video Extraction│     │ Knowledge Graph │
│ - YouTube/Bili  │     │ - Entity Extract│
│ - Subtitle/Audio│     │ - Relation Map  │
│ - Whisper ASR  │     │ - Graph Storage │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Content Analysis     │
         │    Engine             │
         │  - Doc Generation     │
         │  - Entity Recog (LLM) │
         │  - GraphRAG           │
         └───────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  Document Output│     │  Knowledge Graph│
│  Markdown/Word  │     │  Neo4j/GraphDB  │
└─────────────────┘     └─────────────────┘
```

---

## Demo Implementation

### Directory Structure

```
video2kb/
├── README.md                    # This document
├── requirements.txt             # Dependencies
├── config.py                   # Configuration file
├── video_extractor.py          # Video extraction module
├── transcriber.py              # ASR transcription module
├── entity_extractor.py         # Entity extraction module
├── knowledge_graph.py          # Knowledge graph module
├── document_generator.py       # Document generation module
├── main.py                     # Main program
├── data/                       # Data directory
│   ├── raw/                    # Raw video/audio
│   ├── transcripts/            # Transcribed text
│   └── docs/                   # Generated documents
└── mcp_server/                 # MCP server (optional)
    └── server.py
```

---

## Quick Start

### 1. Install Dependencies

```bash
cd /data/research/video-analysis
pip install -r requirements.txt
```

**Hugging Face Mirror (required for mainland China networks):**

Since Hugging Face access is unstable within mainland China, you need to set a mirror source:

```bash
# Temporary (current session only)
export HF_ENDPOINT=https://hf-mirror.com

# Permanent (write to shell config file)
echo 'export HF_ENDPOINT=https://hf-mirror.com' >> ~/.zshrc
source ~/.zshrc
```

**System Dependency: FFmpeg** (required for both Whisper ASR and yt-dlp audio extraction):

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg
```

### 2. Configure Environment Variables

Edit `config.py` or create a `.env` file:

```python
# API Keys
OPENAI_API_KEY="sk-xxx"        # If using OpenAI Whisper
ZAI_API_KEY="xxx"               # Zhipu GLM
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="password"
```

### 3. Run the Demo

```bash
# Extract and analyze a single video
python main.py --url "https://www.youtube.com/watch?v=xxx"

# Batch processing
python main.py --batch urls.txt
```

---

## OpenClaw Skills Configuration

This project includes OpenClaw skills for AI agent integration. Each skill has specific environment variable requirements.

### Skill Environment Variables

| Skill | Required Environment Variables | Optional Environment Variables |
|-------|-------------------------------|--------------------------------|
| `video-extract` | - | - |
| `whisper-transcribe` | - | `WHISPER_MODEL` (default: `base`) |
| `text-summarize` | - | `ZAI_API_KEY`, `OPENAI_API_KEY`, `LLM_MODEL` |
| `entity-extract` | - | `ZAI_API_KEY`, `OPENAI_API_KEY`, `SPACY_MODEL` |
| `knowledge-graph` | - | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `GRAPH_DB_TYPE` |
| `report-generator` | - | `DOC_FORMAT` |

### Environment Variable Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `ZAI_API_KEY` | Zhipu AI API key for LLM features | - |
| `OPENAI_API_KEY` | OpenAI API key for LLM features | - |
| `WHISPER_MODEL` | Whisper model size | `base` (tiny/base/small/medium/large) |
| `LLM_MODEL` | LLM model name | `glm-5` |
| `SPACY_MODEL` | spaCy NLP model | `zh_core_web_sm` |
| `NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | `password` |
| `GRAPH_DB_TYPE` | Graph database type | `networkx` (networkx/neo4j) |
| `DOC_FORMAT` | Report output format | `markdown` (markdown/word/both) |

### Setup for OpenClaw

1. Copy `.env.example` to `.env` and configure your values:
```bash
cp .env.example .env
# Edit .env with your API keys and preferences
```

2. The `.openclaw` directory structure:
```
.openclaw/
├── workspace-video-kb/    # Workspace configuration
│   ├── SOUL.md            # Agent behavior
│   ├── AGENTS.md          # Orchestration flow
│   ├── TOOLS.md           # Tool permissions
│   └── USER.md            # User preferences
└── skills/                # Individual skills
    ├── video-extract/
    ├── whisper-transcribe/
    ├── text-summarize/
    ├── entity-extract/
    ├── knowledge-graph/
    └── report-generator/
```

3. When using OpenClaw, environment variables from `.env` are automatically loaded by the skill scripts.

---

## Technical Deep Dive

### 1. Entity Extraction Strategy

**Approach A: Rule-based (fast but imprecise)**
```python
import spacy
nlp = spacy.load("zh_core_web_sm")
doc = nlp(text)
entities = [(ent.text, ent.label_) for ent in doc.ents]
```

**Approach B: LLM-based (precise but slower)**
```python
from llama_index.core.node_parser import EntityExtractor
extractor = EntityExtractor()
entities = extractor.extract(text)
```

**Recommended:** Hybrid strategy - use rules for initial filtering, then LLM for fine-grained extraction

---

### 2. GraphRAG Implementation

**Core Approach:**
1. Segment the video by time
2. Extract entities and relationships from each segment
3. Entities as nodes, relationships as edges
4. Edge attributes include: timestamp, video URL, confidence

**Neo4j Cypher Example:**
```cypher
// Create entity
CREATE (p:Person {name: "张三", source: "video_001"})

// Create relationship
MATCH (p1:Person {name: "张三"})
MATCH (p2:Person {name: "李四"})
CREATE (p1)-[:KNOWS {video: "https://...", timestamp: 120}]->(p2)
```

**At Query Time:**
```cypher
// Find all content related to a specific entity
MATCH (e:Entity {name: "关键词"})-[:MENTIONED_IN]->(v:Video)
RETURN v.url, v.timestamp
```

---

### 3. MCP Server Design

**Sample MCP Server Structure:**

```python
from mcp.server import Server
from mcp.types import Tool

server = Server("video-analysis")

@server.tool()
async def extract_video(url: str) -> str:
    """Extract video content and summarize"""
    # Call your video extraction module
    return summary

@server.tool()
async def query_graph(entity: str) -> str:
    """Query the knowledge graph"""
    # Query Neo4j
    return results
```

**Claude / OpenClaw Integration:**
- Call your tools via MCP
- Natural language -> video/graph queries

---

## Future Directions

1. **Multimodal Analysis**
   - Incorporate video frames (visual content)
   - Audio sentiment analysis

2. **Real-time Stream Processing**
   - Live stream real-time transcription
   - Real-time entity extraction

3. **RAG Enhancement**
   - Integrate vector databases (Chroma/Qdrant)
   - Hybrid retrieval (graph + vector)

4. **Frontend Visualization**
   - D3.js / Cytoscape.js for knowledge graph display
   - Video timeline linked with entities

---

## References

- [GraphRAG Paper](https://arxiv.org/abs/2404.16130)
- [MCP Protocol Documentation](https://modelcontextprotocol.io/)
- [Neo4j GraphRAG Tutorial](https://neo4j.com/developer-blog/graphrag/)
- [Whisper Official Documentation](https://github.com/openai/whisper)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp)

---

## Next Steps

Check out the code implementation of each module, and run `main.py` to get started!
