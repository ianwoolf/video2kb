#!/usr/bin/env python3
"""
Text Summarization - Summarize long text into structured documents, extracting key points and viewpoints

Usage:
    python3 summarize.py --input-file data/transcripts/test.txt
    python3 summarize.py --text "Text content to summarize"
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)


def summarize_with_llm(text: str, api_key: str, provider: str = "zai", model: str = "glm-4.7", max_length: int = 500) -> dict:
    """Generate a structured summary using an LLM API"""
    prompt = f"""Please summarize the following text and extract key points and core viewpoints.

Requirements:
1. Generate a summary within {max_length} characters
2. Extract 3-10 key points
3. Return JSON format: {{"summary": "...", "key_points": ["Point 1", "Point 2", ...]}}

Text content:
{text[:8000]}
"""

    if provider == "zai" and api_key:
        try:
            from zhipuai import ZhipuAI
            client = ZhipuAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content
            # Try to extract JSON from the response
            result = _parse_llm_response(content, text, max_length)
            return result
        except Exception as e:
            logger.warning("LLM API call failed: %s, falling back to rule-based", e)

    elif provider == "openai" and api_key:
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content
            result = _parse_llm_response(content, text, max_length)
            return result
        except Exception as e:
            logger.warning("OpenAI API call failed: %s, falling back to rule-based", e)

    # Fallback to rule-based method
    return _rule_based_summarize(text, max_length)


def _parse_llm_response(content: str, original_text: str, max_length: int) -> dict:
    """Try to parse JSON from LLM response; fall back to rule-based on failure"""
    try:
        # Try direct parsing
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try extracting from a markdown code block
    import re
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Parsing failed; use LLM output as summary
    return _rule_based_summarize(content if len(content) < len(original_text) else original_text, max_length)


def _rule_based_summarize(text: str, max_length: int = 500) -> dict:
    """Rule-based text summarization (fallback method)"""
    sentences = []
    for sep in ["。", "！", "？", ".", "!", "?"]:
        if sep in text:
            sentences = [s.strip() for s in text.split(sep) if s.strip()]
            break

    if not sentences:
        sentences = [text]

    # Take the first N sentences as the summary
    summary = ""
    key_points = []
    for sent in sentences:
        if len(summary) + len(sent) + 1 <= max_length:
            summary += sent + "。"
            if len(key_points) < 10:
                key_points.append(sent)
        else:
            break

    if not summary:
        summary = text[:max_length]

    return {
        "summary": summary,
        "key_points": key_points[:10],
        "word_count": len(summary),
    }


def main():
    parser = argparse.ArgumentParser(description="Summarize long text into structured documents, extracting key points and viewpoints")
    parser.add_argument("--text", help="Text content to summarize")
    parser.add_argument("--input-file", help="Read text to summarize from a file")
    parser.add_argument("--max-length", type=int, default=500, help="Maximum summary length (default: 500)")
    parser.add_argument("--output-dir", default="data/docs", help="Output directory (default: data/docs)")
    args = parser.parse_args()

    # Read text
    if args.input_file:
        text = Path(args.input_file).read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        parser.error("Must specify --text or --input-file")

    # Try LLM or rule-based method
    api_key = os.getenv("ZAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    provider = "zai" if os.getenv("ZAI_API_KEY") else "openai"
    model = os.getenv("LLM_MODEL", "glm-4.7")

    if api_key:
        result = summarize_with_llm(text, api_key, provider=provider, model=model, max_length=args.max_length)
    else:
        result = _rule_based_summarize(text, args.max_length)

    # Save result
    out_path = Path(args.output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    if args.input_file:
        base_name = Path(args.input_file).stem + "_summary"
    else:
        base_name = "summary"
    summary_path = out_path / f"{base_name}.json"
    summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
