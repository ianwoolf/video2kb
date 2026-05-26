#!/usr/bin/env python3
"""
视频内容提取 — 支持 YouTube 和 Bilibili
提取元数据、字幕，并可选下载音频

Usage:
    python3 extract_video.py --url "https://youtube.com/watch?v=xxx" [--download-audio] [--output-dir data/raw]
"""
import argparse
import json
import logging
import re
import sys
from pathlib import Path

import yt_dlp

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

# 完全屏蔽 yt-dlp 输出
class _NullLogger:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass

YT_DLP_OPTIONS = {
    "format": "bestaudio/best",
    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
    "quiet": True,
    "no_warnings": True,
    "logger": _NullLogger(),
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "extractor_args": {
        "bilibili": {
            "session_id": "",
        }
    },
}


def detect_platform(url: str) -> str:
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    elif "bilibili.com" in url or "b23.tv" in url:
        return "bilibili"
    else:
        raise ValueError(f"不支持的平台: {url}")


def extract_youtube_id(url: str) -> str:
    pattern = r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    raise ValueError("无效的 YouTube URL")


def extract_bilibili_id(url: str) -> str:
    """从 Bilibili URL 提取 video_id（BV 号）"""
    # BV 开头
    match = re.search(r'(BV[a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    # AV 开头
    match = re.search(r'av(\d+)', url, re.IGNORECASE)
    if match:
        return match.group(0)
    raise ValueError("无法从 Bilibili URL 提取视频 ID")


def extract_video(url: str, download_audio: bool = False, output_dir: str = "data/raw") -> dict:
    platform = detect_platform(url)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    result = {
        "platform": platform,
        "url": url,
        "title": "",
        "description": "",
        "duration": 0,
        "video_id": "",
        "channel": "",
        "published_at": None,
        "transcript": "",
        "audio_path": "",
    }

    # 提取 video_id
    try:
        if platform == "youtube":
            result["video_id"] = extract_youtube_id(url)
        elif platform == "bilibili":
            result["video_id"] = extract_bilibili_id(url)
    except ValueError as e:
        logger.warning("提取 video_id 失败: %s", e)

    # 获取视频元数据
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            result["title"] = info.get("title", "")
            result["description"] = info.get("description", "")
            result["duration"] = info.get("duration", 0) or 0
            result["channel"] = info.get("uploader", "") or info.get("channel", "") or ""
            # published_at 可能是 timestamp 或字符串
            pub = info.get("upload_date", "") or ""
            if pub:
                result["published_at"] = pub  # 格式 YYYYMMDD
            # 如果之前没提取到 video_id，从 info 中获取
            if not result["video_id"]:
                result["video_id"] = info.get("id", "")
            logger.info("提取视频: %s", result["title"])
    except Exception as e:
        logger.error("获取视频信息失败: %s", e)

    # YouTube 字幕（优先尝试）
    has_subtitle = False
    if platform == "youtube" and result["video_id"]:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.get_transcript(
                result["video_id"], languages=["zh", "zh-Hans", "zh-CN", "en"]
            )
            result["transcript"] = "\n".join([t["text"] for t in transcript_list])
            logger.info("字幕长度: %d 字符", len(result["transcript"]))
            has_subtitle = True
        except Exception as e:
            logger.info("无可用字幕: %s", e)

    # Bilibili 无字幕提取，需要 ASR
    if platform == "bilibili":
        logger.info("Bilibili 平台: 需要语音识别（无字幕提取）")
        has_subtitle = False

    # 下载音频：显式要求 或 无字幕
    if download_audio or not has_subtitle:
        try:
            options = YT_DLP_OPTIONS.copy()
            options["outtmpl"] = str(out_path / "%(title)s.%(ext)s")
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")
                result["audio_path"] = filename
                logger.info("音频已保存: %s", filename)
        except Exception as e:
            logger.error("下载音频失败: %s", e)

    return result


def main():
    parser = argparse.ArgumentParser(description="从 YouTube/Bilibili 提取视频元数据、字幕及可选音频下载")
    parser.add_argument("--url", required=True, help="视频 URL")
    parser.add_argument("--download-audio", action="store_true", help="下载音频文件")
    parser.add_argument("--output-dir", default="data/raw", help="输出目录 (默认: data/raw)")
    args = parser.parse_args()

    result = extract_video(args.url, download_audio=args.download_audio, output_dir=args.output_dir)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
