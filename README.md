# video2kb — 视频内容分析与知识图谱系统

将 YouTube/Bilibili 视频转化为结构化知识：提取内容 → AI 分析 → 构建知识图谱 → 语义检索。

## 架构概览

```
Pipeline (采集分析)                    KB (知识服务)
┌─────────────────┐               ┌──────────────────────┐
│ 视频抓取        │               │ POST /api/ingest     │
│ (yt-dlp)        │               │ GET  /api/query/*    │
├─────────────────┤    HTTP       ├──────────┬───────────┤
│ ASR 转写        │ ──────────→  │ Neo4j    │ ChromaDB  │
│ (Whisper)       │   REST JSON  │ 图数据库  │ 向量库    │
├─────────────────┤               ├──────────┴───────────┤
│ LLM 总结/实体   │               │ FastAPI              │
│ (智谱/OpenAI)   │               │                      │
└─────────────────┘               └──────────────────────┘
```

## 快速开始

### 前置条件

- Docker + Docker Compose
- FFmpeg（Pipeline 容器内已包含）
- 智谱 API Key（LLM + Embedding）

### 1. 配置

```bash
cp .env.example .env
# 编辑 .env，填入 ZAI_API_KEY 等
```

### 2. 启动 KB（知识服务）

```bash
cd kb && docker-compose up -d
# API: http://localhost:8000
# Neo4j UI: http://localhost:7474
# API 文档: http://localhost:8000/docs
```

### 3. 分析视频

```bash
# Docker 方式
cd pipeline && docker-compose run pipeline --url "https://www.youtube.com/watch?v=xxx"

# 或本地运行（需安装依赖）
cd pipeline && pip install -r requirements.txt
python run.py --url "https://www.youtube.com/watch?v=xxx"
```

### 4. 查询

```bash
# 查询实体
curl -H "X-API-Key: your_key" http://localhost:8000/api/query/entity?name=张三

# 语义搜索
curl -H "X-API-Key: your key" -H "Content-Type: application/json" \
  -d '{"query": "人工智能的未来发展"}' \
  http://localhost:8000/api/query/search
```

## 目录结构

```
video2kb/
├── shared/                     # Pipeline/KB 共享数据模型
│   └── schema.py
├── pipeline/                   # 采集分析服务
│   ├── run.py                  # 入口
│   ├── scripts/
│   │   ├── extract_video.py    # 视频提取
│   │   ├── transcribe.py       # ASR 转写
│   │   ├── summarize.py        # LLM 总结
│   │   ├── extract_entities.py # 实体/关系提取
│   │   ├── data_client.py      # KB 通信
│   │   ├── generate_report.py  # 报告生成
│   │   └── run_pipeline.py     # Pipeline 编排
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
├── kb/                         # 知识服务
│   ├── app/
│   │   ├── main.py             # FastAPI 入口
│   │   ├── config.py           # 配置管理
│   │   ├── routers/            # API 路由
│   │   └── services/           # 业务逻辑
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
├── scripts/                    # 原始独立脚本
└── .env.example
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/ingest | 接收分析结果，存入图数据库+向量库 |
| GET | /api/query/entity?name=xxx | 查询实体及关联关系 |
| GET | /api/query/video?url=xxx | 查询视频的所有实体 |
| POST | /api/query/search | 语义搜索（自然语言查询） |
| GET | /api/query/subgraph?entity=xxx&depth=2 | 子图遍历 |

## 技术栈

- **视频提取**: yt-dlp, youtube-transcript-api
- **语音识别**: faster-whisper
- **LLM**: 智谱 GLM (zhipuai SDK) / OpenAI
- **图数据库**: Neo4j (Docker)
- **向量库**: ChromaDB
- **Embedding**: 智谱 embedding-3 API
- **API 框架**: FastAPI
- **容器化**: Docker + Docker Compose

## License

MIT
