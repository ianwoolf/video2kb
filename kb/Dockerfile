FROM python:3.11-slim

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制 shared 包（Pipeline/KB 共享的数据模型）
COPY shared/ /app/shared/

# 复制 local embedder 模块
COPY kb/embed/ /app/embed/

# 安装 Python 依赖
COPY kb/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 复制 KB 应用代码
COPY kb/ /app/

# 数据目录
RUN mkdir -p /app/data/{archive,qdrant}

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
