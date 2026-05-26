FROM python:3.11-slim

# 系统依赖：ffmpeg（Whisper ASR + yt-dlp 音频提取必需）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制 shared 包（Pipeline/KB 共享的数据模型）
COPY shared/ /app/shared/

# 安装 Python 依赖
COPY pipeline/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 预下载 Whisper 模型（避免运行时首次下载）
ENV HF_ENDPOINT=https://hf-mirror.com
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base', download_root='/app/models')"

# spaCy 中文模型
RUN python -m spacy download zh_core_web_sm

# 复制 Pipeline 应用代码
COPY pipeline/ /app/

# 数据目录
RUN mkdir -p /app/data/{raw,transcripts,docs,logs,pending}

CMD ["python", "run.py"]
