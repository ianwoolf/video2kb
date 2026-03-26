"""
知识图谱模块 - Neo4j/NetworkX
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import asdict
from enum import Enum

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

import networkx as nx
from entity_extractor import Entity, Relation

from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, GRAPH_DB_TYPE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GraphDBType(Enum):
    NEO4J = "neo4j"
    NETWORKX = "networkx"


class KnowledgeGraph:
    """知识图谱管理器"""

    def __init__(self, db_type: str = GRAPH_DB_TYPE):
        self.db_type = db_type

        if db_type == GraphDBType.NEO4J.value:
            self.driver = self._init_neo4j()
            logger.info(f"Connected to Neo4j: {NEO4J_URI}")
        else:
            self.graph = nx.MultiDiGraph()
            logger.info("Using NetworkX graph")

    def _init_neo4j(self):
        """初始化Neo4j连接"""
        if not NEO4J_AVAILABLE:
            raise ImportError("Neo4j driver not installed")

        driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USER, NEO4J_PASSWORD)
        )

        # 测试连接
        with driver.session() as session:
            session.run("RETURN 1")

        return driver

    def add_video(self, video_url: str, title: str, timestamp: float = 0):
        """添加视频节点"""
        if self.db_type == GraphDBType.NEO4J.value:
            self._neo4j_add_video(video_url, title, timestamp)
        else:
            self.graph.add_node(
                video_url,
                type="Video",
                title=title,
                timestamp=timestamp
            )

    def add_entity(self, entity: Entity, video_url: str):
        """添加实体节点"""
        if self.db_type == GraphDBType.NEO4J.value:
            self._neo4j_add_entity(entity, video_url)
        else:
            self.graph.add_node(
                entity.text,
                type=entity.label,
                confidence=entity.confidence
            )
            # 实体-视频边
            self.graph.add_edge(
                entity.text,
                video_url,
                relation="MENTIONED_IN",
                timestamp=entity.start
            )

    def add_relation(self, relation: Relation, video_url: str):
        """添加关系边"""
        if self.db_type == GraphDBType.NEO4J.value:
            self._neo4j_add_relation(relation, video_url)
        else:
            self.graph.add_edge(
                relation.source,
                relation.target,
                relation=relation.relation,
                video_url=video_url,
                timestamp=relation.timestamp,
                context=relation.context,
                confidence=relation.confidence
            )

    def add_transcript_segment(
        self,
        text: str,
        start_time: float,
        end_time: float,
        video_url: str,
        entities: List[Entity]
    ):
        """添加转录片段及其实体"""
        segment_id = f"{video_url}#{start_time}"

        if self.db_type == GraphDBType.NEO4J.value:
            self._neo4j_add_segment(segment_id, text, start_time, end_time, video_url)
        else:
            self.graph.add_node(
                segment_id,
                type="Segment",
                text=text,
                start=start_time,
                end=end_time,
                video_url=video_url
            )

        # 添加实体和关系
        for entity in entities:
            self.add_entity(entity, video_url)

    def query_entity(self, entity_name: str) -> List[Dict[str, Any]]:
        """查询实体的所有关系"""
        if self.db_type == GraphDBType.NEO4J.value:
            return self._neo4j_query_entity(entity_name)
        else:
            return self._networkx_query_entity(entity_name)

    def query_video_entities(self, video_url: str) -> List[Dict[str, Any]]:
        """查询视频中的所有实体"""
        if self.db_type == GraphDBType.NEO4J.value:
            return self._neo4j_query_video_entities(video_url)
        else:
            return self._networkx_query_video_entities(video_url)

    def query_timeline(self, video_url: str, entity_name: str) -> List[Dict[str, Any]]:
        """查询实体在视频中的时间线"""
        if self.db_type == GraphDBType.NEO4J.value:
            return self._neo4j_query_timeline(video_url, entity_name)
        else:
            return self._networkx_query_timeline(video_url, entity_name)

    # Neo4j实现
    def _neo4j_add_video(self, url: str, title: str, timestamp: float):
        with self.driver.session() as session:
            session.run("""
                MERGE (v:Video {url: $url})
                SET v.title = $title, v.timestamp = $timestamp
            """, url=url, title=title, timestamp=timestamp)

    def _neo4j_add_entity(self, entity: Entity, video_url: str):
        with self.driver.session() as session:
            session.run("""
                MERGE (e:Entity {name: $name})
                SET e.type = $type, e.confidence = $confidence
                MERGE (v:Video {url: $video_url})
                MERGE (e)-[r:MENTIONED_IN]->(v)
                SET r.timestamp = $timestamp
            """, name=entity.text, type=entity.label, confidence=entity.confidence,
                video_url=video_url, timestamp=entity.start)

    def _neo4j_add_relation(self, relation: Relation, video_url: str):
        with self.driver.session() as session:
            session.run("""
                MERGE (e1:Entity {name: $source})
                MERGE (e2:Entity {name: $target})
                MERGE (e1)-[r:RELATED_TO]->(e2)
                SET r.relation = $relation, r.video_url = $video_url,
                    r.timestamp = $timestamp, r.context = $context
            """, source=relation.source, target=relation.target,
                relation=relation.relation, video_url=video_url,
                timestamp=relation.timestamp, context=relation.context)

    def _neo4j_add_segment(self, segment_id: str, text: str, start: float, end: float, video_url: str):
        with self.driver.session() as session:
            session.run("""
                MERGE (s:Segment {id: $id})
                SET s.text = $text, s.start = $start, s.end = $end, s.video_url = $video_url
                MERGE (v:Video {url: $video_url})
                MERGE (s)-[r:BELONGS_TO]->(v)
            """, id=segment_id, text=text, start=start, end=end, video_url=video_url)

    def _neo4j_query_entity(self, entity_name: str) -> List[Dict]:
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity {name: $name})-[r]->(other)
                RETURN e, r, other
            """, name=entity_name)
            return [record.data() for record in result]

    def _neo4j_query_video_entities(self, video_url: str) -> List[Dict]:
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity)-[:MENTIONED_IN]->(v:Video {url: $url})
                RETURN e.name, e.type, e.confidence
            """, url=video_url)
            return [record.data() for record in result]

    def _neo4j_query_timeline(self, video_url: str, entity_name: str) -> List[Dict]:
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity {name: $name})-[r:MENTIONED_IN]->(v:Video {url: $url})
                RETURN r.timestamp ORDER BY r.timestamp
            """, name=entity_name, url=video_url)
            return [record.data() for record in result]

    # NetworkX实现
    def _networkx_query_entity(self, entity_name: str) -> List[Dict]:
        if entity_name not in self.graph:
            return []

        results = []
        for neighbor, edge_data in self.graph[entity_name].items():
            results.append({
                "entity": neighbor,
                "relation": edge_data.get("relation", "CONNECTED"),
                **edge_data
            })
        return results

    def _networkx_query_video_entities(self, video_url: str) -> List[Dict]:
        if video_url not in self.graph:
            return []

        entities = []
        for entity, edge_data in self.graph.predecessors(video_url):
            entities.append({
                "name": entity,
                **self.graph.nodes[entity]
            })
        return entities

    def _networkx_query_timeline(self, video_url: str, entity_name: str) -> List[Dict]:
        if entity_name not in self.graph or video_url not in self.graph[entity_name]:
            return []

        edges = self.graph[entity_name][video_url]
        if not isinstance(edges, dict):
            edges = {"timestamp": 0}

        return [{"timestamp": edges.get("timestamp", 0)}]

    def close(self):
        """关闭连接"""
        if self.db_type == GraphDBType.NEO4J.value:
            self.driver.close()


# CLI测试
if __name__ == "__main__":
    import sys

    db_type = sys.argv[1] if len(sys.argv) > 1 else "networkx"

    kg = KnowledgeGraph(db_type)

    # 测试数据
    video_url = "https://youtube.com/watch?v=test123"
    kg.add_video(video_url, "测试视频", 0)

    entity1 = Entity(text="张三", label="PERSON", start=0, end=2)
    entity2 = Entity(text="北京", label="GPE", start=10, end=12)
    kg.add_entity(entity1, video_url)
    kg.add_entity(entity2, video_url)

    relation = Relation(source="张三", target="北京", relation="LIVES_IN", timestamp=5)
    kg.add_relation(relation, video_url)

    # 查询
    print(f"Entity '张三' relations: {kg.query_entity('张三')}")
    print(f"Video entities: {kg.query_video_entities(video_url)}")
    print(f"Timeline: {kg.query_timeline(video_url, '张三')}")

    kg.close()
