FROM python:3.11-slim

# 系统依赖：ffmpeg（Whisper ASR 必需）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY transcoder/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 预下载 Whisper 模型（避免运行时首次下载）
ENV HF_ENDPOINT=https://hf-mirror.com
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base', download_root='/app/models')" || true

COPY transcoder/ /app/
COPY shared/ /app/shared/

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
