#!/usr/bin/env python3
"""
实体与关系提取 — 使用 spaCy NER + LLM 从文本中提取命名实体及其关系
输出字段对齐 shared/schema.py: name, type, description, confidence

Usage:
    python3 extract_entities.py --input "张三是北京大学的教授" [--source-url "URL"] [--use-llm]
    python3 extract_entities.py --input-file data/transcripts/test.txt [--use-llm]
"""
import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

ENTITY_TYPES = ["PERSON", "ORG", "GPE", "EVENT", "WORK_OF_ART"]


@dataclass
class Entity:
    """实体 — 字段对齐 schema.py Entity 模型"""
    name: str           # schema: name（原 text）
    type: str           # schema: type（原 label）
    start: int = 0
    end: int = 0
    description: str = ""  # schema: description（原 context）
    confidence: float = 1.0


@dataclass
class Relation:
    """实体间关系 — 字段对齐 schema.py Relation 模型"""
    source: str
    target: str
    relation: str = ""
    description: str = ""  # schema: description（原 context）
    timestamp: Optional[float] = None
    confidence: float = 1.0


def load_spacy():
    try:
        import spacy
        try:
            return spacy.load(os.getenv("SPACY_MODEL", "zh_core_web_sm"))
        except OSError:
            logger.warning("spaCy 模型未找到，将仅使用 LLM")
            return None
    except ImportError:
        logger.warning("spaCy 未安装，将仅使用 LLM")
        return None


def extract_spacy(nlp, text: str) -> List[Entity]:
    if not nlp:
        return []
    doc = nlp(text)
    entities = []
    for ent in doc.ents:
        if ent.label_ in ENTITY_TYPES:
            entities.append(Entity(
                name=ent.text,
                type=ent.label_,
                start=ent.start_char,
                end=ent.end_char,
            ))
    logger.info("spaCy 提取了 %d 个实体", len(entities))
    return entities


def extract_llm(text: str, source_url: str = "") -> tuple:
    """使用 LLM 提取实体和关系，字段对齐 schema.py"""
    api_key = os.getenv("ZAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return [], []

    provider = "zai" if os.getenv("ZAI_API_KEY") else "openai"
    model = os.getenv("LLM_MODEL", "glm-4.7")

    prompt = f"""请从以下文本中提取实体和关系。

文本来源: {source_url or "未知视频"}
文本内容:
{text[:2000]}

要求：
1. 识别所有重要实体（人物、地点、组织、概念等）
2. 识别实体之间的关系
3. 为每个实体提供简要描述
4. 每个关系包括：源实体、目标实体、关系类型、关系描述

返回 JSON 格式：
{{
  "entities": [
    {{"name": "实体名称", "type": "Person|Organization|Location|Event|Concept|WorkOfArt|Product|Other", "description": "实体简要描述", "confidence": 0.9}}
  ],
  "relations": [
    {{"source": "实体A", "target": "实体B", "relation": "关系类型", "description": "关系描述", "confidence": 0.8}}
  ]
}}"""

    try:
        content = _call_llm(provider, api_key, model, prompt)
        return _parse_llm_extraction(content)
    except Exception as e:
        logger.error("LLM 提取失败: %s", e)
        return [], []


def _call_llm(provider: str, api_key: str, model: str, prompt: str) -> str:
    if provider == "zai":
        from zhipuai import ZhipuAI
        client = ZhipuAI(api_key=api_key)
        response = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
        return response.choices[0].message.content
    else:
        import openai
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
        return response.choices[0].message.content


def _parse_llm_extraction(content: str) -> tuple:
    """解析 LLM 提取结果，字段对齐 schema.py"""
    entities = []
    relations = []
    try:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        text = match.group(1) if match else content
        data = json.loads(text)
        for e in data.get("entities", []):
            entities.append(Entity(
                name=e.get("name", e.get("text", "")),  # 兼容旧的 text 字段
                type=e.get("type", e.get("label", "Other")),
                start=0,
                end=0,
                description=e.get("description", ""),
                confidence=e.get("confidence", 1.0),
            ))
        for r in data.get("relations", []):
            relations.append(Relation(
                source=r["source"],
                target=r["target"],
                relation=r.get("relation", ""),
                description=r.get("description", ""),
                confidence=r.get("confidence", 1.0),
            ))
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("解析 LLM 提取结果失败: %s", e)
    return entities, relations


def merge_entities(spacy_entities: List[Entity], llm_entities: List[Entity]) -> List[Entity]:
    seen = set()
    merged = []
    for entity in spacy_entities + llm_entities:
        key = (entity.name, entity.type)
        if key not in seen:
            seen.add(key)
            merged.append(entity)
    return merged


def extract(text: str, source_url: str = "", use_llm: bool = True) -> dict:
    """提取实体和关系，返回格式对齐 schema.py"""
    nlp = load_spacy()
    spacy_entities = extract_spacy(nlp, text)

    llm_entities, llm_relations = [], []
    if use_llm:
        llm_entities, llm_relations = extract_llm(text, source_url)

    all_entities = merge_entities(spacy_entities, llm_entities)

    # 转为字典输出，字段对齐 schema.py
    result = {
        "entities": [
            {
                "name": e.name,
                "type": e.type,
                "description": e.description,
                "confidence": e.confidence,
            }
            for e in all_entities
        ],
        "relations": [
            {
                "source": r.source,
                "target": r.target,
                "relation": r.relation,
                "description": r.description,
                "confidence": r.confidence,
            }
            for r in llm_relations
        ],
    }
    logger.info("提取了 %d 个实体, %d 个关系", len(all_entities), len(llm_relations))
    return result


def main():
    parser = argparse.ArgumentParser(description="从文本中提取命名实体及其关系")
    parser.add_argument("--input", help="要分析的文本内容")
    parser.add_argument("--input-file", help="从文件读取要分析的文本")
    parser.add_argument("--source-url", default="", help="来源视频 URL")
    parser.add_argument("--use-llm", action="store_true", help="使用 LLM 增强提取（需要 API Key）")
    args = parser.parse_args()

    if args.input_file:
        text = Path(args.input_file).read_text(encoding="utf-8")
    elif args.input:
        text = args.input
    else:
        parser.error("必须指定 --input 或 --input-file")

    result = extract(text, source_url=args.source_url, use_llm=args.use_llm)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
