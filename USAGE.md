# Usage Guide

## Quick Start

### 1. Install Dependencies

```bash
cd /data/research/video-analysis
pip install -r requirements.txt
```

**Hugging Face Mirror (required for networks in China):**

Since Hugging Face access is unstable in China, you need to set up a mirror source:

```bash
# Temporary (current session only)
export HF_ENDPOINT=https://hf-mirror.com

# Permanent (write into shell config file)
echo 'export HF_ENDPOINT=https://hf-mirror.com' >> ~/.zshrc
source ~/.zshrc
```

**System Dependency: FFmpeg** (required by both Whisper ASR and yt-dlp audio extraction):

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg
```

### 2. Configure Environment Variables (Optional)

Create a `.env` file:

```bash
# API Keys (optional; defaults from config file will be used if not set)
OPENAI_API_KEY=sk-xxx
ZAI_API_KEY=xxx
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

### 3. Run the Demo

#### Option A: Analyze a Single Video (Using Subtitles)

```bash
python main.py --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --no-audio
```

#### Option B: Analyze a Single Video (Using ASR)

```bash
python main.py --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

#### Option C: Batch Processing

Create a `urls.txt` file:
```
https://www.youtube.com/watch?v=xxx1
https://www.youtube.com/watch?v=xxx2
https://www.bilibili.com/video/xxx3
```

Run:
```bash
python main.py --batch urls.txt
```

#### Option D: Query the Knowledge Graph

```bash
python main.py --query "entity name"
```

---

## Output Description

### Document Structure

Generated Markdown documents are located in the `data/docs/` directory and contain:

- **Video Info**: Source, link, duration
- **Summary**: Content overview
- **Transcript**: Full subtitles or ASR results
- **Entity Recognition**: People, places, organizations, etc.
- **Entity Relations**: Semantic relationships between entities
- **Timeline**: Entity appearance timestamps within the video

### Knowledge Graph

- **Neo4j Mode**: Data is stored in a Neo4j database and can be queried using Cypher
- **NetworkX Mode**: Data is stored in memory, suitable for quick testing

---

## Advanced Usage

### 1. Custom Entity Extraction

Modify the prompt in `entity_extractor.py`, or integrate your own LLM API.

### 2. Vector Search

Enable vector search:

```python
# config.py
ENABLE_VECTOR_SEARCH = "true"
```

### 3. MCP Server Integration

Create a custom MCP Server to let Claude/OpenClaw directly call your tools.

See: `mcp_server/server.py` (optional implementation)

---

## Frequently Asked Questions

### Q: ASR is slow, what should I do?

**A:** Use a smaller Whisper model:
```python
# config.py
WHISPER_MODEL = "tiny"  # or "base"
```

### Q: Neo4j connection failed?

**A:** Check your configuration:
```python
# config.py
GRAPH_DB_TYPE = "networkx"  # Use NetworkX for testing first
```

Or make sure Neo4j is running:
```bash
docker run -d --name neo4j \
    -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/password \
    neo4j:5.15
```

### Q: YouTube subtitle retrieval failed?

**A:** Use ASR (download audio):
```bash
python main.py --url "..."  # omit --no-audio
```

---

## Extension Suggestions

1. **Multimodal Analysis**: Incorporate video frame content
2. **Real-time Processing**: Use streaming APIs
3. **Visualization**: Display the knowledge graph with D3.js/Cytoscape.js
4. **RAG Enhancement**: Integrate a vector database

---

## References

- [GraphRAG Paper](https://arxiv.org/abs/2404.16130)
- [Whisper Documentation](https://github.com/openai/whisper)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp)
- [Neo4j Cypher](https://neo4j.com/docs/cypher-manual/)
