#!/usr/bin/env python3
"""
Video Content Extraction - Supports YouTube and Bilibili
Extract metadata, subtitles, and optionally download audio from a video URL

Usage:
    python3 extract_video.py --url "https://youtube.com/watch?v=xxx" [--download-audio] [--output-dir data/raw]
"""
import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

import yt_dlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

# Completely suppress yt-dlp output
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
}


def detect_platform(url: str) -> str:
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    elif "bilibili.com" in url or "b23.tv" in url:
        return "bilibili"
    else:
        raise ValueError(f"Unsupported platform: {url}")


def extract_youtube_id(url: str) -> str:
    pattern = r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    raise ValueError("Invalid YouTube URL")


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
        "transcript": "",
        "audio_path": "",
    }

    # Fetch metadata
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            result["title"] = info.get("title", "")
            result["description"] = info.get("description", "")
            result["duration"] = info.get("duration", 0)
            if platform == "youtube":
                result["video_id"] = extract_youtube_id(url)
            logger.info("Extracted video: %s", result["title"])
    except Exception as e:
        logger.error("Failed to get video info: %s", e)

    # YouTube subtitles (try to get them first)
    has_subtitle = False
    if platform == "youtube":
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            video_id = extract_youtube_id(url)
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["zh", "zh-Hans", "en"])
            result["transcript"] = "\n".join([t["text"] for t in transcript_list])
            logger.info("Transcript length: %d chars", len(result["transcript"]))
            has_subtitle = True
        except Exception as e:
            logger.info("No subtitle available: %s", e)

    # Bilibili - no subtitle support, always need audio
    if platform == "bilibili":
        logger.info("Bilibili platform: ASR required (no subtitle extraction)")
        has_subtitle = False

    # Download audio if: explicitly requested OR no subtitle available
    if download_audio or not has_subtitle:
        try:
            options = YT_DLP_OPTIONS.copy()
            options["outtmpl"] = str(out_path / "%(title)s.%(ext)s")
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")
                result["audio_path"] = filename
                logger.info("Audio saved to: %s", filename)
        except Exception as e:
            logger.error("Failed to download audio: %s", e)

    return result


def main():
    parser = argparse.ArgumentParser(description="Extract video metadata, subtitles, and optionally download audio from YouTube/Bilibili")
    parser.add_argument("--url", required=True, help="Video URL")
    parser.add_argument("--download-audio", action="store_true", help="Download audio file")
    parser.add_argument("--output-dir", default="data/raw", help="Output directory (default: data/raw)")
    args = parser.parse_args()

    result = extract_video(args.url, download_audio=args.download_audio, output_dir=args.output_dir)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
