#!/usr/bin/env python3
"""
Analyzer 流水线 — 视频采集分析流水线

通过模块级 import 调用各步骤函数（而非 subprocess），方便未来并发改造。
Step 5 (原 graph_store) 替换为调用 data_client.py 发送数据到 Server。

Usage:
    python3 run_pipeline.py --url "https://youtube.com/watch?v=xxx"
"""
import argparse
import json
import logging
import os
import sys
import tempfile
from datetime import datetime
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
from pipeline.scripts.transcribe import transcribe
from pipeline.scripts.summarize import summarize_with_llm, _rule_based_summarize
from pipeline.scripts.extract_entities import extract
from pipeline.scripts.generate_report import generate_report


def _build_video_info(raw: dict) -> VideoInfo:
    """将 extract_video 的原始输出转换为 schema VideoInfo"""
    platform = Platform(raw.get("platform", "youtube"))
    published_at = raw.get("published_at")
    if published_at and len(published_at) == 8:
        # YYYYMMDD → YYYY-MM-DD
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
    """将 summarize 的原始输出转换为 schema Summary"""
    return Summary(
        full_summary=raw.get("full_summary", raw.get("summary", "")),
        key_points=raw.get("key_points", []),
        word_count=raw.get("word_count", 0),
    )


def _build_entities(raw_entities: list) -> list:
    """将 extract_entities 的原始实体列表转换为 schema Entity 列表"""
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
    """将 extract_entities 的原始关系列表转换为 schema Relation 列表"""
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
    """将 transcribe 的 segments 转换为 schema TranscriptSegment 列表"""
    return [
        TranscriptSegment(
            start=float(s.get("start", 0)),
            end=float(s.get("end", 0)),
            text=s.get("text", ""),
        )
        for s in raw_segments
    ]


def analyze(
    url: str,
    send: bool = True,
    local_report: bool = True,
    fmt: str = "markdown",
    use_llm: bool = True,
    output_base: str = "data",
) -> dict:
    """执行完整的视频分析流水线"""
    # 计算各目录路径
    data_base = Path(output_base)
    raw_dir = data_base / "raw"
    transcript_dir = data_base / "transcripts"
    docs_dir = data_base / "docs"
    pending_dir = data_base / "pending"

    logger.info("=== 开始处理: %s ===", url)

    # ── Step 1: 视频提取 ──────────────────────────────────────────
    logger.info("[1/5] 提取视频信息...")
    video_raw = extract_video(url, download_audio=False, output_dir=str(raw_dir))

    transcript = video_raw.get("transcript", "")
    audio_path = video_raw.get("audio_path", "")
    transcript_segments = []

    logger.info("视频标题: %s", video_raw.get("title", "(未知)"))
    logger.info("有字幕: %s", bool(transcript))
    logger.info("有音频: %s", bool(audio_path))

    # ── Step 2: 语音转文字 ────────────────────────────────────────
    if not transcript and audio_path:
        logger.info("[2/5] 语音转文字...")
        try:
            whisper_model = os.getenv("WHISPER_MODEL", "base")
            trans_result = transcribe(
                audio_path,
                language="zh",
                model_size=whisper_model,
                output_dir=str(transcript_dir),
            )
            transcript = trans_result.get("text", "")
            transcript_segments = trans_result.get("segments", [])
            video_raw["transcript"] = transcript
            if transcript:
                logger.info("转写成功，长度: %d 字符", len(transcript))
            else:
                logger.warning("转写完成但返回空文本")
        except Exception as e:
            logger.error("转写失败: %s", e)
            return {"error": f"转写失败: {e}", "video_info": video_raw}
    else:
        if transcript:
            logger.info("[2/5] 使用已提取的字幕（跳过 ASR）")
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

    # ── Step 5: 构建 IngestPayload 并发送到 Server ────────────────
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
    )

    payload_dict = payload.model_dump(mode="json")

    send_result = {"status": "skipped"}
    if send:
        logger.info("发送数据到 Server...")
        send_result = send_to_kb(payload_dict, pending_dir=pending_dir)
    else:
        logger.info("跳过发送（--send=false）")

    # ── 可选: 生成本地报告 ────────────────────────────────────────
    report_path = ""
    if local_report:
        logger.info("生成本地报告...")
        docs_dir.mkdir(parents=True, exist_ok=True)

        # 保存中间结果文件
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
    }

    logger.info("=== 流水线完成！===")
    logger.info("  实体: %d, 关系: %d, 发送状态: %s", final["entity_count"], final["relation_count"], final["send_status"])
    return final


def main():
    parser = argparse.ArgumentParser(
        description="视频采集分析流水线 — Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", required=True, help="视频 URL")
    parser.add_argument("--output-dir", default="data", help="数据输出根目录 (默认: data)")
    parser.add_argument("--send", action="store_true", default=True, help="发送到 Server (默认: true)")
    parser.add_argument("--no-send", dest="send", action="store_false", help="不发送到 Server")
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
