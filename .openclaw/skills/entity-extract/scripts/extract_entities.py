#!/usr/bin/env python3
"""
Entity and Relation Extraction - Extract named entities and relations from text using spaCy NER + LLM

Usage:
    python3 extract_entities.py --input "Zhang San is a professor at Peking University" [--source-url "URL"] [--use-llm]
    python3 extract_entities.py --input-file data/transcripts/test.txt [--use-llm]
"""
import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

# Entity extraction configuration
ENTITY_TYPES = ["PERSON", "ORG", "GPE", "EVENT", "WORK_OF_ART"]


@dataclass
class Entity:
    text: str
    label: str
    start: int
    end: int
    confidence: float = 1.0


@dataclass
class Relation:
    source: str
    target: str
    relation: str
    timestamp: Optional[float] = None
    context: str = ""
    confidence: float = 1.0


def load_spacy():
    try:
        import spacy
        try:
            return spacy.load(os.getenv("SPACY_MODEL", "zh_core_web_sm"))
        except OSError:
            logger.warning("spaCy model not found, will use LLM only")
            return None
    except ImportError:
        logger.warning("spaCy not installed, will use LLM only")
        return None


def extract_spacy(nlp, text: str) -> List[Entity]:
    if not nlp:
        return []
    doc = nlp(text)
    entities = []
    for ent in doc.ents:
        if ent.label_ in ENTITY_TYPES:
            entities.append(Entity(text=ent.text, label=ent.label_, start=ent.start_char, end=ent.end_char))
    logger.info("Extracted %d entities with spaCy", len(entities))
    return entities


def extract_llm(text: str, source_url: str = "") -> tuple:
    """Extract entities and relations using LLM"""
    api_key = os.getenv("ZAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return [], []

    provider = "zai" if os.getenv("ZAI_API_KEY") else "openai"
    model = os.getenv("LLM_MODEL", "glm-4.7")

    prompt = f"""Please extract entities and relations from the following text.

Text source: {source_url or "Unknown video"}
Text content:
{text[:2000]}

Requirements:
1. Identify all important entities (people, places, organizations, concepts, etc.)
2. Identify relations between entities
3. Each relation should include: source entity, target entity, relation type

Return JSON format:
{{
  "entities": [
    {{"text": "Entity name", "label": "PERSON|ORG|GPE|CONCEPT", "confidence": 0.9}}
  ],
  "relations": [
    {{"source": "Entity A", "target": "Entity B", "relation": "Relation type", "confidence": 0.8}}
  ]
}}"""

    try:
        content = _call_llm(provider, api_key, model, prompt)
        return _parse_llm_extraction(content)
    except Exception as e:
        logger.error("LLM extraction failed: %s", e)
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
    entities = []
    relations = []
    try:
        import re
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        text = match.group(1) if match else content
        data = json.loads(text)
        for e in data.get("entities", []):
            entities.append(Entity(text=e["text"], label=e.get("label", "UNKNOWN"), start=0, end=0, confidence=e.get("confidence", 1.0)))
        for r in data.get("relations", []):
            relations.append(Relation(source=r["source"], target=r["target"], relation=r.get("relation", ""), confidence=r.get("confidence", 1.0)))
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to parse LLM extraction response: %s", e)
    return entities, relations


def merge_entities(spacy_entities: List[Entity], llm_entities: List[Entity]) -> List[Entity]:
    seen = set()
    merged = []
    for entity in spacy_entities + llm_entities:
        key = (entity.text, entity.label)
        if key not in seen:
            seen.add(key)
            merged.append(entity)
    return merged


def extract(text: str, source_url: str = "", use_llm: bool = True) -> dict:
    nlp = load_spacy()
    spacy_entities = extract_spacy(nlp, text)

    llm_entities, llm_relations = [], []
    if use_llm:
        llm_entities, llm_relations = extract_llm(text, source_url)

    all_entities = merge_entities(spacy_entities, llm_entities)

    result = {
        "entities": [asdict(e) for e in all_entities],
        "relations": [asdict(r) for r in llm_relations],
    }
    logger.info("Extracted %d entities, %d relations", len(all_entities), len(llm_relations))
    return result


def main():
    parser = argparse.ArgumentParser(description="Extract named entities and their relations from text")
    parser.add_argument("--input", help="Text content to analyze")
    parser.add_argument("--input-file", help="Read text to analyze from a file")
    parser.add_argument("--source-url", default="", help="Source video URL")
    parser.add_argument("--use-llm", action="store_true", help="Use LLM-enhanced extraction (requires API Key)")
    args = parser.parse_args()

    if args.input_file:
        text = Path(args.input_file).read_text(encoding="utf-8")
    elif args.input:
        text = args.input
    else:
        parser.error("Must specify --input or --input-file")

    result = extract(text, source_url=args.source_url, use_llm=args.use_llm)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
