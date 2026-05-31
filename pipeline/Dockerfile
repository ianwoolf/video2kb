FROM python:3.11-slim

# 系统依赖：ffmpeg（yt-dlp 音频提取必需）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pipeline/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# spaCy 中文模型
RUN python -m spacy download zh_core_web_sm || true

COPY pipeline/ /app/
COPY shared/ /app/shared/

CMD ["python", "run.py"]
