"""
配置文件 - 视频/图谱分析Demo
"""
import os
from pathlib import Path

# 项目路径
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
TRANSCRIPT_DIR = DATA_DIR / "transcripts"
DOC_DIR = DATA_DIR / "docs"

# 创建目录
for d in [DATA_DIR, RAW_DIR, TRANSCRIPT_DIR, DOC_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ZAI_API_KEY = os.getenv("ZAI_API_KEY", "e775a982c443469c937e84e9ba2818ee.O9zpnmdiqTQZTRhl")

# Neo4j 配置
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")  # 与docker-compose.yml中的密码匹配

# 模型配置
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")  # tiny/base/small/medium/large
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "zai")  # zai / openai
LLM_MODEL = os.getenv("LLM_MODEL", "glm-4.7")

# 向量嵌入模型
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "shibing624/text2vec-base-chinese")

# 视频提取配置
YT_DLP_OPTIONS = {
    "format": "bestaudio/best",
    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
    "outtmpl": f"{RAW_DIR}/%(title)s.%(ext)s",
}

# 实体提取配置
ENTITY_EXTRACTION_ENABLED = True
ENTITY_TYPES = ["PERSON", "ORG", "GPE", "EVENT", "WORK_OF_ART"]

# GraphRAG配置
GRAPH_DB_TYPE = os.getenv("GRAPH_DB_TYPE", "neo4j")  # neo4j / networkx
ENABLE_VECTOR_SEARCH = os.getenv("ENABLE_VECTOR_SEARCH", "true").lower() == "true"

# 文档生成配置
DOC_FORMAT = os.getenv("DOC_FORMAT", "markdown")  # markdown / word / both
SUMMARY_MAX_LENGTH = 500

# 中文NLP模型
SPACY_MODEL = os.getenv("SPACY_MODEL", "zh_core_web_sm")
