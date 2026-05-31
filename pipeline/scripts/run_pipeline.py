#!/usr/bin/env python3
"""
Pipeline 流水线 — 视频采集分析编排器

通过模块级 import 调用各步骤函数，通过 HTTP 调用外部服务。
有字幕的视频直接使用字幕，无字幕的上传音频到 Storage + Transcoder 解码。

Usage:
    python3 run_pipeline.py --url "https://youtube.com/watch?v=xxx"
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

# 添加项目根目录到 path，以便 import shared
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from shared.schema import (
    Entity, EntityType, IngestPayload, Platform, Relation,
    Summary, TranscriptSegment, VideoInfo,
)

from pipeline.scripts.data_client import send_to_kb

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

# 模块化导入各步骤
from pipeline.scripts.extract_video import extract_video
from pipeline.scripts.summarize import summarize_with_llm, _rule_based_summarize
from pipeline.scripts.extract_entities import extract
from pipeline.scripts.generate_report import generate_report

# Transcoder 可用时用外部服务，否则 fallback 到本地 Whisper
TRANSCODER_ENABLED = os.getenv("TRANSCODER_URL", "") != ""
STORAGE_ENABLED = os.getenv("STORAGE_URL", "") != ""


def _build_video_info(raw: dict) -> VideoInfo:
    """将 extract_video 的原始输出转换为 schema VideoInfo"""
    platform = Platform(raw.get("platform", "youtube"))
    published_at = raw.get("published_at")
    if published_at and len(published_at) == 8:
        published_at = f"{published_at[:4]}-{published_at[4:6]}-{published_at[6:8]}"
    return VideoInfo(
        platform=platform,
        url=raw.get("url", ""),
        title=raw.get("title", ""),
        description=raw.get("description", ""),
        duration=raw.get("duration", 0),
        video_id=raw.get("video_id", ""),
        channel=raw.get("channel", ""),
        published_at=published_at,
    )


def _build_summary(raw: dict) -> Summary:
    return Summary(
        full_summary=raw.get("full_summary", raw.get("summary", "")),
        key_points=raw.get("key_points", []),
        word_count=raw.get("word_count", 0),
    )


def _build_entities(raw_entities: list) -> list:
    entities = []
    for e in raw_entities:
        entities.append(Entity(
            name=e.get("name", e.get("text", "")),
            type=e.get("type", e.get("label", "Other")),
            description=e.get("description", e.get("context", "")),
            confidence=float(e.get("confidence", 1.0)),
        ))
    return entities


def _build_relations(raw_relations: list) -> list:
    relations = []
    for r in raw_relations:
        relations.append(Relation(
            source=r.get("source", ""),
            target=r.get("target", ""),
            relation=r.get("relation", ""),
            description=r.get("description", r.get("context", "")),
            confidence=float(r.get("confidence", 1.0)),
        ))
    return relations


def _build_transcript_segments(raw_segments: list) -> list:
    return [
        TranscriptSegment(
            start=float(s.get("start", 0)),
            end=float(s.get("end", 0)),
            text=s.get("text", ""),
        )
        for s in raw_segments
    ]


def _transcribe_via_external(audio_path: str, video_id: str = "") -> dict:
    """
    通过 Storage + Transcoder 服务进行音频转写。

    流程：上传音频到 Storage → 提交 Transcoder 任务 → 轮询完成 → 返回结果。
    """
    from pipeline.clients.storage_client import upload_file
    from pipeline.clients.transcoder_client import submit_task, poll_task

    logger.info("  [外部 ASR] 上传音频到 Storage: %s", audio_path)
    storage_result = upload_file(
        file_path=audio_path,
        metadata={"video_id": video_id, "type": "audio"},
    )
    if not storage_result:
        raise RuntimeError("上传音频到 Storage 失败")

    audio_storage_id = storage_result["storage_id"]
    audio_storage_path = storage_result.get("storage_path", "")
    logger.info("  [外部 ASR] 音频已存储: %s", audio_storage_id)

    # 提交转写任务
    logger.info("  [外部 ASR] 提交转写任务...")
    task_result = submit_task(
        storage_id=audio_storage_id,
        storage_path=audio_storage_path,
        language="zh",
        model=os.getenv("WHISPER_MODEL", "base"),
    )
    if not task_result:
        raise RuntimeError("提交转写任务失败")

    task_id = task_result["task_id"]
    logger.info("  [外部 ASR] 任务已提交: %s，等待完成...", task_id)

    # 轮询任务完成
    transcode_result = poll_task(task_id)

    if transcode_result["status"] == "completed":
        logger.info("  [外部 ASR] 转写完成: %d 字符", len(transcode_result.get("text", "")))
        return {
            "text": transcode_result.get("text", ""),
            "segments": transcode_result.get("segments", []),
            "audio_storage_id": audio_storage_id,
            "audio_storage_path": audio_storage_path,
            "transcript_storage_id": transcode_result.get("transcript_storage_id", ""),
            "transcript_text_storage_id": transcode_result.get("transcript_text_storage_id", ""),
            "transcript_srt_storage_id": transcode_result.get("transcript_srt_storage_id", ""),
            "source": "external",
        }
    elif transcode_result["status"] == "failed":
        raise RuntimeError(f"转写任务失败: {transcode_result.get('error', 'unknown')}")
    else:
        raise RuntimeError(f"转写任务超时 (last status: {transcode_result.get('last_status', 'unknown')})")


def _transcribe_local(audio_path: str, video_id: str = "") -> dict:
    """
    本地 Whisper fallback（不经过 Storage/Transcoder）。
    当外部服务不可用时使用。
    """
    from pipeline.scripts.transcribe import transcribe
    whisper_model = os.getenv("WHISPER_MODEL", "base")

    logger.info("  [本地 ASR] faster-whisper 转写: %s (model=%s)", audio_path, whisper_model)
    trans_result = transcribe(
        audio_path,
        language="zh",
        model_size=whisper_model,
        output_dir=str(Path(audio_path).parent.parent / "transcripts"),
    )
    logger.info("  [本地 ASR] 转写完成: %d 字符", len(trans_result.get("text", "")))
    return {
        "text": trans_result.get("text", ""),
        "segments": trans_result.get("segments", []),
        "audio_storage_id": "",
        "audio_storage_path": audio_path,
        "transcript_storage_id": "",
        "source": "local",
    }


def analyze(
    url: str,
    send: bool = True,
    local_report: bool = True,
    fmt: str = "markdown",
    use_llm: bool = True,
    output_base: str = "data",
) -> dict:
    """执行完整的视频分析流水线"""
    data_base = Path(output_base)
    raw_dir = data_base / "raw"
    transcript_dir = data_base / "transcripts"
    docs_dir = data_base / "docs"
    pending_dir = data_base / "pending"

    logger.info("=== 开始处理: %s ===", url)
    logger.info("外部服务: Storage=%s, Transcoder=%s",
                "✅" if STORAGE_ENABLED else "❌",
                "✅" if TRANSCODER_ENABLED else "❌")

    # ── Step 1: 视频提取 ──────────────────────────────────────────
    logger.info("[1/5] 提取视频信息...")
    video_raw = extract_video(url, download_audio=False, output_dir=str(raw_dir))

    transcript = video_raw.get("transcript", "")
    audio_path = video_raw.get("audio_path", "")
    transcript_segments = []
    video_id = video_raw.get("video_id", "")

    logger.info("视频标题: %s", video_raw.get("title", "(未知)"))
    logger.info("有字幕: %s", bool(transcript))
    logger.info("有音频: %s", bool(audio_path))

    # 存储路径（第三波新增）
    audio_storage_id = ""
    audio_storage_path = ""
    transcript_storage_id = ""

    # ── Step 2: 获取转写文本 ─────────────────────────────────────
    if transcript:
        logger.info("[2/5] 使用已提取的字幕（跳过 ASR）")
    elif audio_path:
        logger.info("[2/5] 语音转文字...")
        try:
            if TRANSCODER_ENABLED and STORAGE_ENABLED:
                trans_result = _transcribe_via_external(audio_path, video_id)
            else:
                logger.info("  外部服务不可用，使用本地 Whisper fallback")
                trans_result = _transcribe_local(audio_path, video_id)

            transcript = trans_result.get("text", "")
            transcript_segments = trans_result.get("segments", [])
            audio_storage_id = trans_result.get("audio_storage_id", "")
            audio_storage_path = trans_result.get("audio_storage_path", "")
            transcript_storage_id = trans_result.get("transcript_storage_id", "")
            video_raw["transcript"] = transcript

            if transcript:
                logger.info("  转写成功，长度: %d 字符", len(transcript))
            else:
                logger.warning("  转写完成但返回空文本")
        except Exception as e:
            logger.error("  转写失败: %s", e)
            return {"error": f"转写失败: {e}", "video_info": video_raw}
    else:
        logger.info("[2/5] 无音频或字幕可用")

    if not transcript:
        logger.error("无可用转写文本，无法继续")
        return {"error": "无可用转写文本", "video_info": video_raw}

    # ── Step 3: 文本摘要 ──────────────────────────────────────────
    logger.info("[3/5] 生成摘要...")
    api_key = os.getenv("ZAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    provider = "zai" if os.getenv("ZAI_API_KEY") else "openai"
    model = os.getenv("LLM_MODEL", "glm-4.7")

    if api_key:
        summary_raw = summarize_with_llm(transcript, api_key, provider=provider, model=model)
    else:
        summary_raw = _rule_based_summarize(transcript)

    # ── Step 4: 实体与关系提取 ────────────────────────────────────
    logger.info("[4/5] 提取实体与关系...")
    entity_raw = extract(transcript, source_url=url, use_llm=use_llm)

    # ── Step 5: 构建 IngestPayload 并发送到 KB ─────────────────────
    logger.info("[5/5] 构建数据包...")
    video_info = _build_video_info(video_raw)
    summary = _build_summary(summary_raw)
    entities = _build_entities(entity_raw.get("entities", []))
    relations = _build_relations(entity_raw.get("relations", []))
    segments = _build_transcript_segments(transcript_segments)

    payload = IngestPayload(
        video=video_info,
        transcript=transcript,
        transcript_segments=segments,
        summary=summary,
        entities=entities,
        relations=relations,
        audio_storage_id=audio_storage_id,
        audio_storage_path=audio_storage_path,
        transcript_storage_id=transcript_storage_id,
    )

    payload_dict = payload.model_dump(mode="json")

    send_result = {"status": "skipped"}
    if send:
        logger.info("发送数据到 KB...")
        send_result = send_to_kb(payload_dict, pending_dir=pending_dir)
    else:
        logger.info("跳过发送（--send=false）")

    # ── 可选: 生成本地报告 ────────────────────────────────────────
    report_path = ""
    if local_report:
        logger.info("生成本地报告...")
        docs_dir.mkdir(parents=True, exist_ok=True)

        video_info_path = docs_dir / "_pipeline_video_info.json"
        video_info_path.write_text(json.dumps(video_raw, ensure_ascii=False, indent=2), encoding="utf-8")

        analysis = {
            "transcript": transcript,
            "full_summary": summary_raw.get("full_summary", summary_raw.get("summary", "")),
            "summary": summary_raw.get("summary", ""),
            "key_points": summary_raw.get("key_points", []),
            "entities": entity_raw.get("entities", []),
            "relations": entity_raw.get("relations", []),
        }
        analysis_path = docs_dir / "_pipeline_analysis.json"
        analysis_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

        report_result = generate_report(
            video_raw, analysis,
            fmt=fmt, output_dir=str(docs_dir),
        )
        report_path = report_result.get("document_path", "")

    # ── 输出结果 ─────────────────────────────────────────────────
    final = {
        "video_info": video_raw,
        "summary": summary_raw.get("full_summary", summary_raw.get("summary", "")),
        "key_points": summary_raw.get("key_points", []),
        "entity_count": len(entities),
        "relation_count": len(relations),
        "send_status": send_result.get("status", "skipped"),
        "document_path": report_path,
        "audio_storage_id": audio_storage_id,
        "transcript_storage_id": transcript_storage_id,
    }

    logger.info("=== 流水线完成！===")
    logger.info("  实体: %d, 关系: %d, 发送状态: %s", final["entity_count"], final["relation_count"], final["send_status"])
    return final


def main():
    parser = argparse.ArgumentParser(
        description="视频采集分析流水线 — Pipeline 编排器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", required=True, help="视频 URL")
    parser.add_argument("--output-dir", default="data", help="数据输出根目录 (默认: data)")
    parser.add_argument("--send", action="store_true", default=True, help="发送到 KB (默认: true)")
    parser.add_argument("--no-send", dest="send", action="store_false", help="不发送到 KB")
    parser.add_argument("--local-report", action="store_true", default=True, help="生成本地报告 (默认: true)")
    parser.add_argument("--no-local-report", dest="local_report", action="store_false", help="不生成本地报告")
    parser.add_argument("--format", choices=["markdown", "word", "both"], default="markdown", help="报告格式 (默认: markdown)")
    parser.add_argument("--no-llm", dest="use_llm", action="store_false", default=True, help="不使用 LLM 增强提取")
    args = parser.parse_args()

    result = analyze(
        args.url,
        send=args.send,
        local_report=args.local_report,
        fmt=args.format,
        use_llm=args.use_llm,
        output_base=args.output_dir,
    )

    if "error" in result:
        print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
