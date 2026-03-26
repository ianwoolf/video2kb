# 使用指南

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

### 2. 配置环境变量（可选）

创建 `.env` 文件：

```bash
# API Keys（可选，默认会使用配置文件中的值）
OPENAI_API_KEY=sk-xxx
ZAI_API_KEY=xxx
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

### 3. 运行Demo

#### 方式A：分析单个视频（使用字幕）

```bash
python main.py --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --no-audio
```

#### 方式B：分析单个视频（使用ASR）

```bash
python main.py --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

#### 方式C：批量处理

创建 `urls.txt` 文件：
```
https://www.youtube.com/watch?v=xxx1
https://www.youtube.com/watch?v=xxx2
https://www.bilibili.com/video/xxx3
```

运行：
```bash
python main.py --batch urls.txt
```

#### 方式D：查询知识图谱

```bash
python main.py --query "实体名"
```

---

## 输出说明

### 文档结构

生成的Markdown文档位于 `data/docs/` 目录，包含：

- **视频信息**: 来源、链接、时长
- **摘要**: 内容概览
- **转录文本**: 完整字幕或ASR结果
- **实体识别**: 人名、地名、组织等
- **实体关系**: 实体间的语义关系
- **时间线**: 实体在视频中的出现时间

### 知识图谱

- **Neo4j模式**: 数据存储在Neo4j数据库中，可用Cypher查询
- **NetworkX模式**: 数据存储在内存中，适合快速测试

---

## 高级用法

### 1. 自定义实体提取

修改 `entity_extractor.py` 中的提示词，或集成自己的LLM API。

### 2. 向量检索

启用向量检索：

```python
# config.py
ENABLE_VECTOR_SEARCH = "true"
```

### 3. MCP Server集成

创建自定义MCP Server，让Claude/OpenClaw直接调用你的工具。

参考：`mcp_server/server.py`（可选实现）

---

## 常见问题

### Q: ASR速度慢怎么办？

**A:** 使用更小的Whisper模型：
```python
# config.py
WHISPER_MODEL = "tiny"  # 或 "base"
```

### Q: Neo4j连接失败？

**A:** 检查配置：
```python
# config.py
GRAPH_DB_TYPE = "networkx"  # 先用NetworkX测试
```

或确保Neo4j正在运行：
```bash
docker run -d --name neo4j \
    -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/password \
    neo4j:5.15
```

### Q: YouTube字幕获取失败？

**A:** 使用ASR（下载音频）：
```bash
python main.py --url "..."  # 不加 --no-audio
```

---

## 扩展建议

1. **多模态分析**: 结合视频帧内容
2. **实时处理**: 使用流式API
3. **可视化**: 用D3.js/Cytoscape.js展示知识图谱
4. **RAG增强**: 集成向量数据库

---

## 参考资料

- [GraphRAG论文](https://arxiv.org/abs/2404.16130)
- [Whisper文档](https://github.com/openai/whisper)
- [yt-dlp文档](https://github.com/yt-dlp/yt-dlp)
- [Neo4j Cypher](https://neo4j.com/docs/cypher-manual/)
