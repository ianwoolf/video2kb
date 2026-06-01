"""
Transcoder Service — 音频解码服务 FastAPI 入口

接收转写任务，用 faster-whisper ASR 推理，异步执行，通过 task_id 查询状态。
转写完成后自动将结果文件上传到 Storage。
"""
from __future__ import annotations

import logging
import os
import sys
import tempfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("transcoder")


def _create_task_handler(app: FastAPI):
    """
    创建任务处理函数（闭包，持有 app 引用以访问 services）。
    此函数在 worker 线程中执行。
    """
    def handler(task_id: str, task_data: dict):
        task_queue = app.state.task_queue
        transcribe_svc = app.state.transcribe_service

        storage_id = task_data["storage_id"]
        language = task_data.get("language", "zh")
        model = task_data.get("model", "base")

        logger.info("Worker: processing task %s (audio=%s, lang=%s, model=%s)",
                     task_id, storage_id, language, model)

        try:
            # 1) 从 Storage 下载音频
            from app.clients.storage_client import download_to_file, upload_file_bytes
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_audio = tmp.name

            if not download_to_file(storage_id, tmp_audio):
                raise RuntimeError(f"Failed to download audio from Storage: {storage_id}")

            # 2) Whisper ASR 转写
            result = transcribe_svc.transcribe(tmp_audio, language=language)

            # 3) 上传转写结果到 Storage
            text_id = None
            srt_id = None

            txt_content = result["text"].encode("utf-8")
            txt_info = upload_file_bytes(
                txt_content,
                filename=f"{storage_id}.txt",
                content_type="text/plain",
                metadata={"video_id": storage_id, "type": "transcript_text"},
            )
            if txt_info:
                text_id = txt_info["storage_id"]

            srt_content = transcribe_svc.format_srt(result["segments"]).encode("utf-8")
            srt_info = upload_file_bytes(
                srt_content,
                filename=f"{storage_id}.srt",
                content_type="text/plain",
                metadata={"video_id": storage_id, "type": "transcript_srt"},
            )
            if srt_info:
                srt_id = srt_info["storage_id"]

            # 4) 清理临时文件
            try:
                os.unlink(tmp_audio)
            except Exception:
                pass

            # 5) 更新任务结果
            task_queue.update_task_status(task_id, "completed", result={
                "text": result["text"],
                "segments": result["segments"],
                "duration": result.get("duration", 0),
                "language": result.get("language", language),
                "audio_storage_id": storage_id,
                "transcript_text_storage_id": text_id or "",
                "transcript_srt_storage_id": srt_id or "",
                "transcript_storage_id": text_id or "",  # 兼容字段
            })

            logger.info("Worker: task %s completed (text_id=%s, srt_id=%s)", task_id, text_id, srt_id)

        except Exception as e:
            logger.error("Worker: task %s failed: %s", task_id, e)
            task_queue.update_task_status(task_id, "failed", error=str(e))

    return handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Transcoder Service...")

    # ── 初始化 TranscribeService（加载 Whisper 模型）──
    from app.services.transcribe_service import TranscribeService
    transcribe_svc = TranscribeService(
        model_size=settings.WHISPER_MODEL,
        device=settings.WHISPER_DEVICE,
    )
    transcribe_svc.load_model()
    app.state.transcribe_service = transcribe_svc

    if not transcribe_svc.available:
        logger.warning("Transcoder: Whisper model not available, tasks will fail")

    # ── 初始化 Task Queue ──
    if settings.TASK_QUEUE == "memory":
        from app.queues.memory import MemoryTaskQueue
        task_queue = MemoryTaskQueue(max_workers=settings.MAX_CONCURRENT_TASKS)
    else:
        raise ValueError(f"Unknown TASK_QUEUE: {settings.TASK_QUEUE}")

    app.state.task_queue = task_queue

    # ── 启动 Worker ──
    handler = _create_task_handler(app)
    task_queue.start_worker(handler)

    logger.info(
        "Transcoder Service ready — model=%s (%s), whisper=%s, queue=%s",
        settings.WHISPER_MODEL, settings.WHISPER_DEVICE,
        "✅" if transcribe_svc.available else "❌",
        settings.TASK_QUEUE,
    )

    yield

    # ── Shutdown ──
    task_queue.stop_worker()
    logger.info("Shutting down Transcoder Service...")


app = FastAPI(
    title="Video2KB — Transcoder Service",
    description="音频解码服务：faster-whisper ASR 推理，异步任务队列",
    version="0.1.0",
    lifespan=lifespan,
)


# ── API Key 中间件 ──
@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if request.url.path in ("/", "/docs", "/openapi.json", "/redoc"):
        return await call_next(request)

    api_key = request.headers.get("X-API-Key", "")
    if api_key != settings.API_KEY:
        return JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Invalid or missing X-API-Key"},
        )
    return await call_next(request)


# ── Routers ──
from app.routers import tasks  # noqa: E402

app.include_router(tasks.router)


# ── Root ──
@app.get("/", tags=["status"])
async def root():
    ts = app.state.transcribe_service if hasattr(app.state, "transcribe_service") else None
    tq = app.state.task_queue if hasattr(app.state, "task_queue") else None
    return {
        "service": "Video2KB — Transcoder Service",
        "version": "0.1.0",
        "whisper": {
            "model": settings.WHISPER_MODEL,
            "available": ts.available if ts else False,
        },
        "queue": {
            "type": settings.TASK_QUEUE,
        },
        "storage_url": settings.STORAGE_URL,
        "endpoints": {
            "transcode": "POST /api/transcode",
            "status": "GET /api/transcode/{task_id}",
        },
    }
