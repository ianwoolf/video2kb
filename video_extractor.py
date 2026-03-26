"""
视频提取模块 - 支持YouTube和Bilibili
"""
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled
import requests

from config import YT_DLP_OPTIONS, RAW_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VideoExtractor:
    """视频内容提取器"""

    def __init__(self, output_dir: Path = RAW_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def detect_platform(self, url: str) -> str:
        """检测视频平台"""
        if "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        elif "bilibili.com" in url or "b23.tv" in url:
            return "bilibili"
        else:
            raise ValueError(f"Unsupported platform: {url}")

    def extract_youtube(self, url: str, download_audio: bool = False) -> Dict[str, Any]:
        """提取YouTube视频信息"""
        video_id = self._extract_youtube_id(url)

        result = {
            "platform": "youtube",
            "video_id": video_id,
            "url": url,
            "title": "",
            "description": "",
            "duration": 0,
            "transcript": "",
            "audio_path": ""
        }

        # 获取视频元数据
        try:
            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                result["title"] = info.get("title", "")
                result["description"] = info.get("description", "")
                result["duration"] = info.get("duration", 0)
                logger.info(f"Extracted video: {result['title']}")
        except Exception as e:
            logger.error(f"Failed to get video info: {e}")

        # 获取字幕
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['zh', 'zh-Hans', 'en'])
            result["transcript"] = "\n".join([t["text"] for t in transcript_list])
            logger.info(f"Transcript length: {len(result['transcript'])} chars")
        except TranscriptsDisabled:
            logger.warning("No transcript available, will use ASR")
        except Exception as e:
            logger.error(f"Failed to get transcript: {e}")

        # 下载音频
        if download_audio:
            audio_path = self._download_audio(url)
            result["audio_path"] = audio_path

        return result

    def extract_bilibili(self, url: str, download_audio: bool = False) -> Dict[str, Any]:
        """提取Bilibili视频信息"""
        # Bilibili需要更复杂的处理，这里简化处理
        result = {
            "platform": "bilibili",
            "url": url,
            "title": "",
            "description": "",
            "duration": 0,
            "transcript": "",
            "audio_path": ""
        }

        try:
            # 使用yt-dlp获取信息（支持bilibili）
            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                result["title"] = info.get("title", "")
                result["description"] = info.get("description", "")
                result["duration"] = info.get("duration", 0)
                logger.info(f"Extracted video: {result['title']}")
        except Exception as e:
            logger.error(f"Failed to get bilibili info: {e}")

        # 下载音频
        if download_audio:
            audio_path = self._download_audio(url)
            result["audio_path"] = audio_path

        # Bilibili字幕提取需要专门的库或解析网页
        # 这里简化，建议使用ASR
        logger.info("Bilibili transcripts require web scraping, will use ASR")

        return result

    def _extract_youtube_id(self, url: str) -> str:
        """从URL提取YouTube视频ID"""
        pattern = r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})'
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        raise ValueError("Invalid YouTube URL")

    def _download_audio(self, url: str) -> Optional[str]:
        """下载音频"""
        options = YT_DLP_OPTIONS.copy()
        options["outtmpl"] = str(self.output_dir / "%(title)s.%(ext)s")

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")
                logger.info(f"Audio saved to: {filename}")
                return filename
        except Exception as e:
            logger.error(f"Failed to download audio: {e}")
            return None

    def extract(self, url: str, download_audio: bool = True) -> Dict[str, Any]:
        """统一入口：提取视频内容"""
        platform = self.detect_platform(url)

        if platform == "youtube":
            return self.extract_youtube(url, download_audio)
        elif platform == "bilibili":
            return self.extract_bilibili(url, download_audio)
        else:
            raise ValueError(f"Unsupported platform: {platform}")


# CLI测试
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python video_extractor.py <video_url>")
        sys.exit(1)

    url = sys.argv[1]
    extractor = VideoExtractor()
    result = extractor.extract(url, download_audio=False)

    print(f"Title: {result['title']}")
    print(f"Duration: {result['duration']}s")
    print(f"Transcript preview: {result['transcript'][:200]}...")
