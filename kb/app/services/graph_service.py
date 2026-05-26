"""
Neo4j 图数据库操作
基于原始 scripts/graph_store.py 和 scripts/graph_query.py 改造。
Neo4j 不可用时优雅降级，不崩溃。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# import shared schema
_SHARED_DIR = str(Path(__file__).resolve().parents[2] / "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)
from schema import IngestPayload  # noqa: E402


class GraphService:
    def __init__(self, driver=None):
        """
        driver: neo4j.GraphDatabase.driver 实例，可为 None（降级模式）
        """
        self._driver = driver
        self._available = False
        if driver is not None:
            try:
                with driver.session() as session:
                    session.run("RETURN 1")
                self._available = True
                logger.info("GraphService: Neo4j connected")
            except Exception as e:
                logger.warning("GraphService: Neo4j connection test failed: %s", e)
                self._driver = None

    @property
    def available(self) -> bool:
        return self._available

    # ── Ingest ────────────────────────────────────────────────────────

    def ingest(self, payload: IngestPayload) -> Dict[str, int]:
        """存储 Video / Entity 节点和关系到 Neo4j。返回统计信息。"""
        if not self._available:
            logger.warning("GraphService.ingest: Neo4j not available, skipping")
            return {"entities_stored": 0, "relations_stored": 0}

        video = payload.video
        entities = payload.entities
        relations = payload.relations

        entities_stored = 0
        relations_stored = 0

        try:
            with self._driver.session() as session:
                # 1) MERGE Video 节点
                session.run(
                    """
                    MERGE (v:Video {url: $url})
                    SET v.title = $title,
                        v.platform = $platform,
                        v.video_id = $video_id,
                        v.channel = $channel,
                        v.duration = $duration,
                        v.description = $description,
                        v.published_at = $published_at
                    """,
                    url=video.url,
                    title=video.title,
                    platform=video.platform.value,
                    video_id=video.video_id,
                    channel=video.channel,
                    duration=video.duration,
                    description=video.description,
                    published_at=video.published_at or "",
                )

                # 2) MERGE Entity 节点 + MENTIONED_IN 关系
                for ent in entities:
                    session.run(
                        """
                        MERGE (e:Entity {name: $name})
                        SET e.type = $type,
                            e.description = $description,
                            e.confidence = $confidence
                        WITH e
                        MATCH (v:Video {url: $url})
                        MERGE (e)-[r:MENTIONED_IN]->(v)
                        """,
                        name=ent.name,
                        type=ent.type,
                        description=ent.description,
                        confidence=ent.confidence,
                        url=video.url,
                    )
                    entities_stored += 1

                # 3) MERGE 关系边
                for rel in relations:
                    session.run(
                        """
                        MERGE (e1:Entity {name: $source})
                        MERGE (e2:Entity {name: $target})
                        MERGE (e1)-[r:RELATED_TO]->(e2)
                        SET r.relation = $relation,
                            r.description = $description,
                            r.confidence = $confidence,
                            r.video_url = $url
                        """,
                        source=rel.source,
                        target=rel.target,
                        relation=rel.relation,
                        description=rel.description,
                        confidence=rel.confidence,
                        url=video.url,
                    )
                    relations_stored += 1

        except Exception as e:
            logger.error("GraphService.ingest error: %s", e)
            raise

        logger.info(
            "GraphService.ingest: stored %d entities, %d relations for %s",
            entities_stored, relations_stored, video.url,
        )
        return {"entities_stored": entities_stored, "relations_stored": relations_stored}

    # ── Query ─────────────────────────────────────────────────────────

    def query_entity(self, name: str) -> List[Dict[str, Any]]:
        """查询实体及其所有关联关系。"""
        if not self._available:
            return [{"error": "neo4j_unavailable", "message": "Neo4j is not connected"}]

        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (e:Entity {name: $name})-[r]-(other)
                RETURN e, r, other, labels(other) AS other_labels
                """,
                name=name,
            )
            records = []
            for record in result:
                data = record.data()
                # 简化返回结构
                records.append({
                    "source": name,
                    "target": data["other"].get("name", str(data["other"])),
                    "relation": dict(data["r"]) if hasattr(data["r"], "items") else str(data["r"]),
                    "target_labels": data["other_labels"],
                })
            return records

    def query_video(self, url: str) -> List[Dict[str, Any]]:
        """查询视频的所有关联实体。"""
        if not self._available:
            return [{"error": "neo4j_unavailable", "message": "Neo4j is not connected"}]

        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (e:Entity)-[r:MENTIONED_IN]->(v:Video {url: $url})
                RETURN e.name AS name, e.type AS type, e.description AS description, e.confidence AS confidence
                """,
                url=url,
            )
            return [record.data() for record in result]

    def query_subgraph(self, entity: str, depth: int = 2) -> Dict[str, Any]:
        """子图遍历：从指定实体出发，遍历指定深度。"""
        if not self._available:
            return {"error": "neo4j_unavailable", "message": "Neo4j is not connected"}

        with self._driver.session() as session:
            result = session.run(
                """
                MATCH path = (e:Entity {name: $name})-[*1..""" + str(min(depth, 5)) + """]-(other:Entity)
                UNWIND nodes(path) AS n
                UNWIND relationships(path) AS r
                WITH COLLECT(DISTINCT {name: n.name, type: n.type, labels: labels(n)}) AS nodes,
                     COLLECT(DISTINCT {source: startNode(r).name, target: endNode(r).name, relation: type(r)}) AS edges
                RETURN nodes, edges
                """,
                name=entity,
            )
            record = result.single()
            if record:
                return record.data()
            return {"nodes": [], "edges": []}
