#!/usr/bin/env python3
"""
文本摘要 — 使用 LLM 或规则方法对长文本进行结构化摘要，提取要点和核心观点

Usage:
    python3 summarize.py --input-file data/transcripts/test.txt
    python3 summarize.py --text "要摘要的文本内容"
"""
import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)


def summarize_with_llm(text: str, api_key: str, provider: str = "zai", model: str = "glm-4.7", max_length: int = 500) -> dict:
    """使用 LLM API 生成结构化摘要，输出字段对齐 schema.py 中的 Summary 模型"""
    prompt = f"""请对以下文本进行摘要，并提取关键要点和核心观点。

要求：
1. 生成不超过 {max_length} 字的摘要
2. 提取 3-10 个关键要点
3. 以 JSON 格式返回: {{"full_summary": "完整摘要", "key_points": ["要点1", "要点2", ...]}}

文本内容：
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
            result = _parse_llm_response(content, text, max_length)
            return result
        except Exception as e:
            logger.warning("LLM API 调用失败: %s, 回退到规则方法", e)

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
            logger.warning("OpenAI API 调用失败: %s, 回退到规则方法", e)

    # 回退到规则方法
    return _rule_based_summarize(text, max_length)


def _parse_llm_response(content: str, original_text: str, max_length: int) -> dict:
    """解析 LLM 响应中的 JSON；解析失败则回退到规则方法"""
    try:
        data = json.loads(content)
        # 字段名对齐 schema.py Summary 模型
        return {
            "full_summary": data.get("full_summary", data.get("summary", "")),
            "key_points": data.get("key_points", []),
            "word_count": len(data.get("full_summary", data.get("summary", ""))),
        }
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块提取
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            return {
                "full_summary": data.get("full_summary", data.get("summary", "")),
                "key_points": data.get("key_points", []),
                "word_count": len(data.get("full_summary", data.get("summary", ""))),
            }
        except json.JSONDecodeError:
            pass

    # 解析失败；将 LLM 输出作为摘要文本
    return _rule_based_summarize(content if len(content) < len(original_text) else original_text, max_length)


def _rule_based_summarize(text: str, max_length: int = 500) -> dict:
    """基于规则的文本摘要（回退方法），输出字段对齐 schema.py"""
    sentences = []
    for sep in ["。", "！", "？", ".", "!", "?"]:
        if sep in text:
            sentences = [s.strip() for s in text.split(sep) if s.strip()]
            break

    if not sentences:
        sentences = [text]

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
        "full_summary": summary,
        "key_points": key_points[:10],
        "word_count": len(summary),
    }


def main():
    parser = argparse.ArgumentParser(description="对长文本进行结构化摘要，提取要点和核心观点")
    parser.add_argument("--text", help="要摘要的文本内容")
    parser.add_argument("--input-file", help="从文件读取要摘要的文本")
    parser.add_argument("--max-length", type=int, default=500, help="摘要最大长度 (默认: 500)")
    parser.add_argument("--output-dir", default="data/docs", help="输出目录 (默认: data/docs)")
    args = parser.parse_args()

    # 读取文本
    if args.input_file:
        text = Path(args.input_file).read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        parser.error("必须指定 --text 或 --input-file")

    # 尝试 LLM 或规则方法
    api_key = os.getenv("ZAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    provider = "zai" if os.getenv("ZAI_API_KEY") else "openai"
    model = os.getenv("LLM_MODEL", "glm-4.7")

    if api_key:
        result = summarize_with_llm(text, api_key, provider=provider, model=model, max_length=args.max_length)
    else:
        result = _rule_based_summarize(text, args.max_length)

    # 保存结果
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
