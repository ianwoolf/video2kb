"""
实体提取模块 - 使用NLP和LLM
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

from config import ZAI_API_KEY, LLM_MODEL, ENTITY_TYPES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """实体数据类"""
    text: str
    label: str  # PERSON, ORG, GPE, etc.
    start: int
    end: int
    confidence: float = 1.0


@dataclass
class Relation:
    """关系数据类"""
    source: str
    target: str
    relation: str
    timestamp: Optional[float] = None
    context: str = ""
    confidence: float = 1.0


class EntityExtractor:
    """实体提取器"""

    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
        self._load_spacy()

    def _load_spacy(self):
        """加载spaCy模型（用于基础NLP）"""
        try:
            import spacy
            try:
                self.nlp = spacy.load("zh_core_web_sm")
                logger.info("Loaded spaCy model: zh_core_web_sm")
            except OSError:
                logger.warning("spaCy model not found, will use LLM only")
                self.nlp = None
        except ImportError:
            logger.warning("spaCy not installed, will use LLM only")
            self.nlp = None

    def extract_spacy(self, text: str) -> List[Entity]:
        """使用spaCy提取实体"""
        if not self.nlp:
            return []

        doc = self.nlp(text)
        entities = []

        for ent in doc.ents:
            if ent.label_ in ENTITY_TYPES:
                entities.append(Entity(
                    text=ent.text,
                    label=ent.label_,
                    start=ent.start_char,
                    end=ent.end_char
                ))

        logger.info(f"Extracted {len(entities)} entities with spaCy")
        return entities

    def extract_llm(self, text: str, video_url: str = "") -> tuple[List[Entity], List[Relation]]:
        """
        使用LLM提取实体和关系

        返回: (entities, relations)
        """
        if not ZAI_API_KEY:
            logger.warning("No LLM API key, skipping LLM extraction")
            return [], []

        prompt = self._build_extraction_prompt(text, video_url)

        try:
            # 这里简化了LLM调用，实际需要使用zhipuai包
            # result = call_llm_api(prompt)
            logger.info("LLM extraction would be called here")
            # 临时返回模拟结果
            return self._mock_llm_extraction(text)
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return [], []

    def _build_extraction_prompt(self, text: str, video_url: str) -> str:
        """构建LLM提取提示词"""
        prompt = f"""
请从以下文本中提取实体和关系。

文本来源：{video_url or "未知视频"}
文本内容：
{text[:2000]}...

要求：
1. 识别所有重要实体（人名、地名、组织、概念等）
2. 识别实体之间的关系
3. 每个关系包含：源实体、目标实体、关系类型

返回JSON格式：
{{
  "entities": [
    {{"text": "实体名", "label": "PERSON|ORG|GPE|CONCEPT", "confidence": 0.9}}
  ],
  "relations": [
    {{"source": "实体A", "target": "实体B", "relation": "关系类型", "confidence": 0.8}}
  ]
}}
"""
        return prompt

    def _mock_llm_extraction(self, text: str) -> tuple[List[Entity], List[Relation]]:
        """模拟LLM提取结果（用于demo）"""
        # 这里只是示例，实际应该调用真实的LLM API
        entities = []
        relations = []

        # 简单规则提取（仅demo用）
        if "中国" in text:
            entities.append(Entity(text="中国", label="GPE", start=0, end=2))
        if "北京" in text:
            entities.append(Entity(text="北京", label="GPE", start=0, end=2))

        logger.info(f"Mock LLM extraction: {len(entities)} entities, {len(relations)} relations")
        return entities, relations

    def extract(self, text: str, video_url: str = "") -> Dict[str, Any]:
        """
        统一入口：提取实体和关系

        Returns:
            {
                "entities": List[Entity],
                "relations": List[Relation]
            }
        """
        # spaCy提取（快速但简单）
        spacy_entities = self.extract_spacy(text)

        # LLM提取（精确但慢）
        llm_entities, llm_relations = [], []
        if self.use_llm:
            llm_entities, llm_relations = self.extract_llm(text, video_url)

        # 合并结果（去重）
        all_entities = self._merge_entities(spacy_entities, llm_entities)

        result = {
            "entities": all_entities,
            "relations": llm_relations,
            "entity_count": len(all_entities),
            "relation_count": len(llm_relations)
        }

        logger.info(f"Extracted {len(all_entities)} entities, {len(llm_relations)} relations")
        return result

    def _merge_entities(self, spacy_entities: List[Entity], llm_entities: List[Entity]) -> List[Entity]:
        """合并spaCy和LLM的实体结果，去重"""
        seen = set()
        merged = []

        for entity in spacy_entities + llm_entities:
            key = (entity.text, entity.label)
            if key not in seen:
                seen.add(key)
                merged.append(entity)

        return merged


# CLI测试
if __name__ == "__main__":
    import sys

    test_text = """
    张三是北京大学的教授，他的人工智能研究获得了中国计算机学会的奖项。
    他在2024年的一次会议上发表演讲，讨论了关于机器学习的话题。
    """

    extractor = EntityExtractor(use_llm=False)
    result = extractor.extract(test_text)

    print(f"Found {result['entity_count']} entities:")
    for entity in result["entities"]:
        print(f"  - {entity.text} ({entity.label})")
