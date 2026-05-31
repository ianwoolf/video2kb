"""
Transcribe Service — faster-whisper ASR 封装

模型在服务启动时加载一次，所有任务共享同一个模型实例。
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TranscribeService:
    """Whisper ASR 推理服务（模型加载一次，推理可复用）"""

    def __init__(self, model_size: str = "base", device: str = "auto"):
        """
        model_size: Whisper 模型大小 (tiny/base/small/medium/large)
        device: auto(自动检测) / cpu / cuda
        """
        self._model_size = model_size
        self._model = None
        self._device = self._detect_device(device)

    @staticmethod
    def _detect_device(device: str) -> str:
        if device != "auto":
            return device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    @property
    def available(self) -> bool:
        return self._model is not None

    def load_model(self):
        """加载 Whisper 模型（启动时调用一次）"""
        try:
            from faster_whisper import WhisperModel
            logger.info("TranscribeService: loading Whisper model '%s' on %s", self._model_size, self._device)
            self._model = WhisperModel(self._model_size, device=self._device)
            logger.info("TranscribeService: model loaded")
        except ImportError:
            logger.error("TranscribeService: faster-whisper not installed")
        except Exception as e:
            logger.error("TranscribeService: failed to load model: %s", e)

    def transcribe(self, audio_path: str, language: str = "zh") -> dict:
        """
        对音频文件执行 ASR 转写。

        Args:
            audio_path: 音频文件路径
            language: 语言代码

        Returns:
            {"text": str, "segments": [{"start", "end", "text"}], "language": str,
             "duration": float}
        """
        if not self._model:
            raise RuntimeError("Whisper model not loaded")

        logger.info("TranscribeService: transcribing %s (lang=%s)", audio_path, language)
        segments_iter, info = self._model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True,
            word_timestamps=False,
        )

        segments_data = []
        full_text = ""
        for seg in segments_iter:
            s = {"start": round(seg.start, 2), "end": round(seg.end, 2), "text": seg.text.strip()}
            segments_data.append(s)
            full_text += seg.text.strip() + "\n"

        duration = segments_data[-1]["end"] if segments_data else 0

        logger.info("TranscribeService: done — %d chars, %d segments, %.1fs",
                     len(full_text.strip()), len(segments_data), duration)
        return {
            "text": full_text.strip(),
            "segments": segments_data,
            "language": info.language,
            "duration": round(duration, 2),
        }

    def format_srt(self, segments: list) -> str:
        """将 segments 格式化为 SRT 字幕格式"""
        lines = []
        for i, seg in enumerate(segments, 1):
            lines.append(str(i))
            lines.append(_format_timestamp(seg["start"]) + " --> " + _format_timestamp(seg["end"]))
            lines.append(seg["text"])
            lines.append("")
        return "\n".join(lines)


def _format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
