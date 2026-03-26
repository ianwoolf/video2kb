# 视频内容分析 Demo - 技术方案与实现

## 项目目标

从 YouTube/Bilibili 视频中提取内容，进行实体识别，并构建知识图谱（GraphRAG），实现：
1. 视频字幕/音频提取
2. 内容总结
3. 实体提取与关系映射
4. 知识图谱存储与检索

---

## 技术栈分析

### 1. 视频内容提取

| 平台 | 推荐工具 | 说明 |
|------|----------|------|
| **YouTube** | `yt-dlp` + `youtube-transcript-api` | 提取字幕、音频、元数据 |
| **Bilibili** | `bilibili-api` + `yt-dlp` | 提取字幕、视频信息 |

**核心库：**
```python
# YouTube
yt-dlp                    # 下载视频/音频/字幕
youtube-transcript-api    # 获取字幕文本

# Bilibili
bilibili-api              # B站API封装
yt-dlp                    # 通用视频下载器
```

**系统依赖：**
- **FFmpeg**：音频/视频处理的核心工具。`yt-dlp` 依赖它从视频文件中提取音频流；Whisper ASR 也依赖它进行音频格式转换。没有 FFmpeg，音频提取和语音识别都无法运行。

---

### 2. 语音识别（ASR）

如果视频没有字幕，需要从音频提取文字：

| 工具 | 优势 | 适用场景 |
|------|------|----------|
| **Whisper** | 高精度、开源、多语言 | 本地部署 |
| **Faster-Whisper** | 速度快 | 大批量处理 |
| **Azure/Google/Tencent ASR** | 云端服务 | 生产环境 |

**推荐：**
```python
openai-whisper          # OpenAI官方模型
faster-whisper          # 优化推理版本
```

**模型下载：**
- **Hugging Face Hub**：Whisper 等模型的权重文件托管在 Hugging Face 上。首次运行时 `faster-whisper` 会通过 `huggingface_hub` 自动下载模型到本地缓存（`~/.cache/huggingface/`）。国内网络访问 Hugging Face 不稳定，需设置镜像源 `HF_ENDPOINT=https://hf-mirror.com` 加速下载。

---

### 3. MCP (Model Context Protocol)

MCP 是 Anthropic 提出的协议，用于连接 AI 模型与外部工具/数据源。

**现有 MCP 工具：**
- `@modelcontextprotocol/server-filesystem` - 文件系统访问
- `@modelcontextprotocol/server-brave-search` - 网页搜索
- `@modelcontextprotocol/server-git` - Git 操作
- 自定义 MCP Server - 封装你的视频分析逻辑

**为什么用 MCP？**
- 标准化协议，便于集成到 Claude 等支持 MCP 的平台
- 轻量级工具调用
- 可扩展性强

---

### 4. GraphRAG (Graph-based Retrieval Augmented Generation)

GraphRAG 结合知识图谱与向量检索，提升 RAG 的效果。

**核心组件：**
1. **实体提取（Entity Extraction）**
   - LLM 从文本中识别实体（人名、地点、概念等）
   - 提取实体间的关系

2. **知识图谱构建**
   - 图数据库存储（Neo4j / Memgraph / NetworkX）
   - 节点 = 实体，边 = 关系

3. **向量嵌入**
   - 实体/文档向量化
   - 支持相似度检索

4. **检索增强**
   - 查询时：实体 → 图谱 → 相关文档
   - 结合向量检索与图遍历

**推荐技术栈：**
```python
# 知识图谱
neo4j                    # 生产级图数据库
memgraph                 # 兼容Neo4j的高性能版本
networkx                 # 轻量级，适合demo

# 向量检索
chromadb / qdrant        # 向量数据库
sentence-transformers    # 中文embedding模型

# 实体提取
spaCy / LlamaIndex       # NLP实体识别
LLM (GLM-4, Claude)      # 基于大模型的提取
```

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户请求                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │    MCP Server         │
         │  (工具/数据封装)      │
         └───────────┬───────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│ 视频提取模块     │     │ 知识图谱模块     │
│ - YouTube/B站   │     │ - 实体提取      │
│ - 字幕/音频     │     │ - 关系映射      │
│ - Whisper ASR  │     │ - 图谱存储      │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   内容分析引擎         │
         │  - 文档生成           │
         │  - 实体识别 (LLM)     │
         │  - GraphRAG          │
         └───────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  文档输出        │     │  知识图谱        │
│  Markdown/Word  │     │  Neo4j/GraphDB  │
└─────────────────┘     └─────────────────┘
```

---

## Demo 实现

### 目录结构

```
/data/research/video-analysis/
├── README.md                    # 本文档
├── requirements.txt             # 依赖
├── config.py                   # 配置文件
├── video_extractor.py          # 视频提取模块
├── transcriber.py              # ASR转录模块
├── entity_extractor.py         # 实体提取模块
├── knowledge_graph.py          # 知识图谱模块
├── document_generator.py       # 文档生成模块
├── main.py                     # 主程序
├── data/                       # 数据目录
│   ├── raw/                    # 原始视频/音频
│   ├── transcripts/            # 转录文本
│   └── docs/                   # 生成的文档
└── mcp_server/                 # MCP服务器（可选）
    └── server.py
```

---

## 快速开始

### 1. 安装依赖

```bash
cd /data/research/video-analysis
pip install -r requirements.txt
```

**Hugging Face 镜像（国内网络必需）：**

由于 Hugging Face 在国内访问不稳定，需要设置镜像源：

```bash
# 临时生效
export HF_ENDPOINT=https://hf-mirror.com

# 永久生效（写入 shell 配置文件）
echo 'export HF_ENDPOINT=https://hf-mirror.com' >> ~/.zshrc
source ~/.zshrc
```

**系统依赖：FFmpeg**（Whisper ASR 和 yt-dlp 音频提取都需要）：

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg
```

### 2. 配置环境变量

编辑 `config.py` 或创建 `.env`：

```python
# API Keys
OPENAI_API_KEY="sk-xxx"        # 如果用OpenAI Whisper
ZAI_API_KEY="xxx"               # 智谱GLM
NEO4J_URI="bolt://localhost:7687"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="password"
```

### 3. 运行Demo

```bash
# 提取并分析单个视频
python main.py --url "https://www.youtube.com/watch?v=xxx"

# 批量处理
python main.py --batch urls.txt
```

---

## 技术深度说明

### 1. 实体提取策略

**方案A：基于规则（快速但不精确）**
```python
import spacy
nlp = spacy.load("zh_core_web_sm")
doc = nlp(text)
entities = [(ent.text, ent.label_) for ent in doc.ents]
```

**方案B：基于LLM（精确但慢）**
```python
from llama_index.core.node_parser import EntityExtractor
extractor = EntityExtractor()
entities = extractor.extract(text)
```

**推荐：** 混合策略 - 规则做初筛，LLM做精细提取

---

### 2. GraphRAG 实现

**核心思路：**
1. 将视频按时间分段
2. 每段提取实体和关系
3. 实体作为节点，关系作为边
4. 边属性包含：时间戳、视频URL、置信度

**Neo4j Cypher示例：**
```cypher
// 创建实体
CREATE (p:Person {name: "张三", source: "video_001"})

// 创建关系
MATCH (p1:Person {name: "张三"})
MATCH (p2:Person {name: "李四"})
CREATE (p1)-[:KNOWS {video: "https://...", timestamp: 120}]->(p2)
```

**检索时：**
```cypher
// 查找与某个实体相关的所有内容
MATCH (e:Entity {name: "关键词"})-[:MENTIONED_IN]->(v:Video)
RETURN v.url, v.timestamp
```

---

### 3. MCP Server 设计

**示例 MCP Server 结构：**

```python
from mcp.server import Server
from mcp.types import Tool

server = Server("video-analysis")

@server.tool()
async def extract_video(url: str) -> str:
    """提取视频内容并总结"""
    # 调用你的视频提取模块
    return summary

@server.tool()
async def query_graph(entity: str) -> str:
    """查询知识图谱"""
    # 查询Neo4j
    return results
```

**Claude / OpenClaw 集成：**
- 通过MCP调用你的工具
- 自然语言 → 视频/图谱查询

---

## 扩展方向

1. **多模态分析**
   - 结合视频帧（视觉内容）
   - 音频情感分析

2. **实时流处理**
   - 直播流实时转录
   - 实时实体提取

3. **RAG增强**
   - 结合向量数据库（Chroma/Qdrant）
   - 混合检索（图谱 + 向量）

4. **前端可视化**
   - D3.js / Cytoscape.js 展示知识图谱
   - 视频时间轴与实体联动

---

## 参考资料

- [GraphRAG 论文](https://arxiv.org/abs/2404.16130)
- [MCP 协议文档](https://modelcontextprotocol.io/)
- [Neo4j GraphRAG 教程](https://neo4j.com/developer-blog/graphrag/)
- [Whisper 官方文档](https://github.com/openai/whisper)
- [yt-dlp 文档](https://github.com/yt-dlp/yt-dlp)

---

## 下一步

查看各模块代码实现，运行 `main.py` 开始使用！
