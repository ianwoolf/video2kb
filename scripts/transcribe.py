#!/usr/bin/env python3
"""
Speech-to-Text - Convert audio files to text using faster-whisper, with Chinese/English support and timestamps

Usage:
    python3 transcribe.py --audio "data/raw/test.mp3" [--language zh] [--model base] [--output-dir data/transcripts]
"""
import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)


def format_timestamp_srt(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millisecs = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"


def transcribe(audio_path: str, language: str = "zh", model_size: str = "base", output_dir: str = "data/transcripts") -> dict:
    from faster_whisper import WhisperModel
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("Loading Whisper model: %s on %s", model_size, device)

    model = WhisperModel(model_size, device=device)

    logger.info("Transcribing: %s", audio_path)
    segments, info = model.transcribe(
        audio_path,
        language=language,
        beam_size=5,
        vad_filter=True,
        word_timestamps=True,
    )

    segments_data = []
    full_text = ""
    for segment in segments:
        seg = {"start": segment.start, "end": segment.end, "text": segment.text.strip()}
        segments_data.append(seg)
        full_text += seg["text"] + "\n"

    result = {
        "audio_path": audio_path,
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": segments_data[-1]["end"] if segments_data else 0,
        "text": full_text.strip(),
        "segments": segments_data,
    }

    logger.info("Transcription complete: %d chars, %d segments", len(full_text), len(segments_data))

    # Save output files
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    base_name = Path(audio_path).stem

    txt_path = out_path / f"{base_name}.txt"
    txt_path.write_text(result["text"], encoding="utf-8")

    srt_path = out_path / f"{base_name}.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments_data, 1):
            f.write(f"{i}\n")
            f.write(f"{format_timestamp_srt(seg['start'])} --> {format_timestamp_srt(seg['end'])}\n")
            f.write(f"{seg['text']}\n\n")

    logger.info("Saved transcript to: %s and %s", txt_path, srt_path)
    return result


def main():
    parser = argparse.ArgumentParser(description="Convert audio files to text using Whisper ASR")
    parser.add_argument("--audio", required=True, help="Audio file path")
    parser.add_argument("--language", default="zh", help="Language code (default: zh)")
    parser.add_argument("--model", default="base", help="Whisper model size: tiny/base/small/medium/large (default: base)")
    parser.add_argument("--output-dir", default="data/transcripts", help="Output directory (default: data/transcripts)")
    args = parser.parse_args()

    result = transcribe(args.audio, language=args.language, model_size=args.model, output_dir=args.output_dir)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
