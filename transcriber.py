"""
语音识别模块 - Whisper ASR
"""
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from faster_whisper import WhisperModel
import torch

from config import WHISPER_MODEL, TRANSCRIPT_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Transcriber:
    """语音转录器"""

    def __init__(self, model_size: str = WHISPER_MODEL, device: str = "auto"):
        """
        初始化Whisper模型

        Args:
            model_size: tiny/base/small/medium/large
            device: auto/cpu/cuda
        """
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        logger.info(f"Loading Whisper model: {model_size} on {device}")
        self.model = WhisperModel(model_size, device=device)
        self.device = device
        self.model_size = model_size

    def transcribe_file(
        self,
        audio_path: str,
        language: str = "zh",
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        转录音频文件

        Args:
            audio_path: 音频文件路径
            language: 语言代码 (zh/en/...)
            output_file: 输出文件路径（可选）

        Returns:
            转录结果字典
        """
        logger.info(f"Transcribing: {audio_path}")

        # 转录
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True,
            word_timestamps=True
        )

        # 收集结果
        segments_data = []
        full_text = ""

        for segment in segments:
            segment_data = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip()
            }
            segments_data.append(segment_data)
            full_text += segment_data["text"] + "\n"

        result = {
            "audio_path": audio_path,
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": segments_data[-1]["end"] if segments_data else 0,
            "text": full_text.strip(),
            "segments": segments_data
        }

        logger.info(f"Transcription complete: {len(full_text)} chars, {len(segments_data)} segments")

        # 保存到文件
        if output_file:
            self._save_transcript(result, output_file)

        return result

    def transcribe_with_timestamps(
        self,
        audio_path: str,
        language: str = "zh"
    ) -> list:
        """
        返回带时间戳的转录片段列表

        Returns:
            [{"start": 0.0, "end": 5.0, "text": "..."}, ...]
        """
        result = self.transcribe_file(audio_path, language)
        return result["segments"]

    def _save_transcript(self, transcript: Dict[str, Any], output_path: str):
        """保存转录结果"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存纯文本
        txt_path = output_path.with_suffix(".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(transcript["text"])

        # 保存带时间戳的格式
        srt_path = output_path.with_suffix(".srt")
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(transcript["segments"], 1):
                f.write(f"{i}\n")
                f.write(f"{self._format_timestamp(seg['start'])} --> {self._format_timestamp(seg['end'])}\n")
                f.write(f"{seg['text']}\n\n")

        logger.info(f"Saved transcript to: {txt_path} and {srt_path}")

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        """格式化时间戳为 SRT 格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"


# CLI测试
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python transcriber.py <audio_file> [language]")
        sys.exit(1)

    audio_file = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else "zh"

    transcriber = Transcriber()
    result = transcriber.transcribe_file(audio_file, language)

    print(f"Language: {result['language']} (confidence: {result['language_probability']:.2f})")
    print(f"Duration: {result['duration']:.2f}s")
    print(f"\nTranscript:\n{result['text'][:500]}...")
