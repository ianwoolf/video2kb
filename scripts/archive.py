#!/usr/bin/env python3
"""
归档模块 — Pipeline 处理完成后将数据保存到 data/archive/{video_id}/

归档内容：
  - meta.json        视频元信息 + 处理状态
  - subtitle.txt     原始字幕/转写文本
  - transcript.txt   ASR 转写文本（如有）
  - audio.mp3        音频文件（如有，可选，可关闭以节省空间）
  - summary.txt      LLM 摘要
  - entities.json    实体+关系

设计原则：
  - 每步完成后逐步写入，失败时已有部分数据可保留
  - 幂等：重复归档同一 video_id 不会覆盖已有文件（除非 force=True）
  - 轻量：纯文件操作，不依赖数据库
"""
from __future__ import annotations

import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_ARCHIVE_DIR = "data/archive"


def _safe_video_id(video_info: dict) -> str:
    """从 video_info 提取安全的归档目录名"""
    vid = video_info.get("video_id", "")
    if not vid:
        # 用 url 的 hash 后 12 位作为 fallback
        url = video_info.get("url", "unknown")
        vid = hex(hash(url) & 0xFFFFFFFFFFFF)[2:].zfill(12)
    # 清理文件名中的非法字符
    import re
    vid = re.sub(r'[<>:"/\\|?*]', '_', vid)
    return vid[:64]


def archive_meta(
    archive_dir: Path,
    video_info: dict,
    status: str = "partial",
    force: bool = False,
) -> Path:
    """归档视频元信息 + 处理状态"""
    meta_file = archive_dir / "meta.json"

    if meta_file.exists() and not force:
        logger.debug("archive_meta: meta.json already exists, skipping")
        return meta_file

    meta = {
        "video_info": video_info,
        "archived_at": datetime.now().isoformat(),
        "status": status,  # partial | complete
    }
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("archive_meta: written %s", meta_file)
    return meta_file


def archive_subtitle(
    archive_dir: Path,
    subtitle_text: str,
    force: bool = False,
) -> Optional[Path]:
    """归档原始字幕文本"""
    if not subtitle_text or not subtitle_text.strip():
        return None

    subtitle_file = archive_dir / "subtitle.txt"
    if subtitle_file.exists() and not force:
        logger.debug("archive_subtitle: subtitle.txt already exists, skipping")
        return subtitle_file

    subtitle_file.write_text(subtitle_text.strip(), encoding="utf-8")
    logger.info("archive_subtitle: written %s", subtitle_file)
    return subtitle_file


def archive_transcript(
    archive_dir: Path,
    transcript_text: str,
    force: bool = False,
) -> Optional[Path]:
    """归档 ASR 转写文本"""
    if not transcript_text or not transcript_text.strip():
        return None

    transcript_file = archive_dir / "transcript.txt"
    if transcript_file.exists() and not force:
        logger.debug("archive_transcript: transcript.txt already exists, skipping")
        return transcript_file

    transcript_file.write_text(transcript_text.strip(), encoding="utf-8")
    logger.info("archive_transcript: written %s", transcript_file)
    return transcript_file


def archive_audio(
    archive_dir: Path,
    audio_path: str,
    force: bool = False,
) -> Optional[Path]:
    """
    归档音频文件（可选，复制到 archive 目录）
    如果音频文件不存在或太大则跳过。
    """
    src = Path(audio_path)
    if not src.exists():
        logger.debug("archive_audio: audio file not found: %s", audio_path)
        return None

    dst = archive_dir / "audio.mp3"
    if dst.exists() and not force:
        logger.debug("archive_audio: audio.mp3 already exists, skipping")
        return dst

    # 检查文件大小，超过 500MB 则跳过
    size_mb = src.stat().st_size / (1024 * 1024)
    if size_mb > 500:
        logger.warning("archive_audio: audio file too large (%.1f MB), skipping", size_mb)
        return None

    shutil.copy2(str(src), str(dst))
    logger.info("archive_audio: copied %s → %s (%.1f MB)", src, dst, size_mb)
    return dst


def archive_summary(
    archive_dir: Path,
    summary_result: dict,
    force: bool = False,
) -> Optional[Path]:
    """归档 LLM 摘要（纯文本格式）"""
    summary_text = summary_result.get("summary", "")
    if not summary_text or not summary_text.strip():
        return None

    summary_file = archive_dir / "summary.txt"
    if summary_file.exists() and not force:
        logger.debug("archive_summary: summary.txt already exists, skipping")
        return summary_file

    summary_file.write_text(summary_text.strip(), encoding="utf-8")
    logger.info("archive_summary: written %s", summary_file)
    return summary_file


def archive_entities(
    archive_dir: Path,
    entity_result: dict,
    force: bool = False,
) -> Optional[Path]:
    """归档实体和关系（JSON 格式）"""
    entities = entity_result.get("entities", [])
    relations = entity_result.get("relations", [])
    if not entities and not relations:
        return None

    entities_file = archive_dir / "entities.json"
    if entities_file.exists() and not force:
        logger.debug("archive_entities: entities.json already exists, skipping")
        return entities_file

    data = {
        "entities": entities,
        "relations": relations,
        "archived_at": datetime.now().isoformat(),
    }
    entities_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("archive_entities: written %s", entities_file)
    return entities_file


def run_archive(
    video_info: dict,
    transcript: str = "",
    subtitle: str = "",
    audio_path: str = "",
    summary_result: Optional[dict] = None,
    entity_result: Optional[dict] = None,
    base_dir: str = DEFAULT_ARCHIVE_DIR,
    force: bool = False,
) -> Dict[str, Any]:
    """
    执行完整归档流程。

    返回归档统计信息。
    """
    video_id = _safe_video_id(video_info)
    archive_dir = Path(base_dir) / video_id
    archive_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== 归档开始: %s ===", video_id)

    stats = {
        "video_id": video_id,
        "archive_dir": str(archive_dir),
        "files": [],
        "errors": [],
    }

    def _do(fn, *args, **kwargs):
        try:
            result = fn(*args, **kwargs)
            if result:
                stats["files"].append(str(result))
        except Exception as e:
            logger.error("归档失败: %s", e)
            stats["errors"].append(str(e))

    # 1) 先归档元信息（partial 状态）
    _do(archive_meta, archive_dir, video_info, status="partial", force=force)

    # 2) 逐步归档各数据
    _do(archive_subtitle, archive_dir, subtitle, force=force)
    _do(archive_transcript, archive_dir, transcript, force=force)
    _do(archive_audio, archive_dir, audio_path, force=force)
    _do(archive_summary, archive_dir, summary_result or {}, force=force)
    _do(archive_entities, archive_dir, entity_result or {}, force=force)

    # 3) 更新元信息为 complete
    _do(archive_meta, archive_dir, video_info, status="complete", force=True)

    logger.info(
        "=== 归档完成: %s → %d 文件, %d 错误 ===",
        video_id, len(stats["files"]), len(stats["errors"]),
    )
    return stats


def main():
    """CLI 入口：从 stdin 读取 JSON 或通过参数传入"""
    import argparse

    parser = argparse.ArgumentParser(description="归档 Pipeline 处理结果")
    parser.add_argument("--video-info", help="Video info JSON string")
    parser.add_argument("--video-info-file", help="Video info JSON file")
    parser.add_argument("--transcript", default="", help="Transcript text")
    parser.add_argument("--transcript-file", help="Transcript text file")
    parser.add_argument("--audio-path", default="", help="Audio file path to copy")
    parser.add_argument("--summary-file", help="Summary result JSON file")
    parser.add_argument("--entities-file", help="Entities result JSON file")
    parser.add_argument("--archive-dir", default=DEFAULT_ARCHIVE_DIR, help="Archive base directory")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    # 读取 video_info
    if args.video_info_file:
        video_info = json.loads(Path(args.video_info_file).read_text(encoding="utf-8"))
    elif args.video_info:
        video_info = json.loads(args.video_info)
    else:
        parser.error("必须指定 --video-info 或 --video-info-file")

    # 读取 transcript
    transcript = args.transcript
    if args.transcript_file:
        transcript = Path(args.transcript_file).read_text(encoding="utf-8")

    # 读取 summary
    summary_result = None
    if args.summary_file:
        summary_result = json.loads(Path(args.summary_file).read_text(encoding="utf-8"))

    # 读取 entities
    entity_result = None
    if args.entities_file:
        entity_result = json.loads(Path(args.entities_file).read_text(encoding="utf-8"))

    stats = run_archive(
        video_info=video_info,
        transcript=transcript,
        audio_path=args.audio_path,
        summary_result=summary_result,
        entity_result=entity_result,
        base_dir=args.archive_dir,
        force=args.force,
    )

    json.dump(stats, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
