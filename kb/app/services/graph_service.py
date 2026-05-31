"""
Memgraph 图数据库操作（替换原 Neo4j）

基于 mgclient 驱动，支持 Memgraph 的 Cypher 方言。
Memgraph 不可用时优雅降级，不崩溃。

配置项：
  ENABLE_GRAPH=true/false  是否启用图数据库
  MEMGRAPH_URI            连接地址
  MEMGRAPH_USER/PASSWORD  认证（Memgraph 默认无认证）
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# import shared schema
_SHARED_DIR = str(Path(__file__).resolve().parents[2] / "shared")
if _SHARED_DIR not in sys.path:
    sys.path.insert(0, _SHARED_DIR)
from schema import IngestPayload  # noqa: E402


class GraphService:
    def __init__(
        self,
        enabled: bool = True,
        uri: str = "bolt://localhost:7687",
        username: str = "",
        password: str = "",
    ):
        """
        enabled: ENABLE_GRAPH 开关
        uri: Memgraph bolt 连接地址
        username/password: Memgraph 认证（默认无认证）
        """
        self._enabled = enabled
        self._uri = uri
        self._available = False
        self._pool = None

        if not enabled:
            logger.info("GraphService: DISABLED by ENABLE_GRAPH=false")
            return

        try:
            import mgclient
            # Memgraph 默认不认证，username/password 为空时传 None
            user = username if username else None
            pwd = password if password else None
            # 测试连接
            conn = mgclient.connect(
                host=_parse_host(uri),
                port=_parse_port(uri),
                username=user,
                password=pwd,
            )
            conn.close()
            self._available = True
            self._username = user
            self._password = pwd
            logger.info("GraphService: Memgraph connected at %s", uri)
        except ImportError:
            logger.warning("GraphService: mgclient not installed, graph disabled")
        except Exception as e:
            logger.warning("GraphService: Memgraph connection failed: %s", e)

    @property
    def available(self) -> bool:
        return self._enabled and self._available

    def _execute(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """执行 Cypher 查询并返回结果列表"""
        import mgclient

        params = parameters or {}
        conn = None
        try:
            conn = mgclient.connect(
                host=_parse_host(self._uri),
                port=_parse_port(self._uri),
                username=self._username,
                password=self._password,
            )
            cursor = conn.execute(query, parameters=params)
            columns = [col.name for col in cursor.description] if cursor.description else []
            results = []
            for row in cursor:
                results.append(dict(zip(columns, row)))
            conn.commit()
            conn.close()
            return results
        except Exception as e:
            logger.error("GraphService._execute error: %s", e)
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            raise

    def _execute_write(self, query: str, parameters: Optional[Dict[str, Any]] = None):
        """执行写操作（INSERT/MERGE/SET 等）"""
        import mgclient

        params = parameters or {}
        conn = None
        try:
            conn = mgclient.connect(
                host=_parse_host(self._uri),
                port=_parse_port(self._uri),
                username=self._username,
                password=self._password,
            )
            conn.execute(query, parameters=params)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("GraphService._execute_write error: %s", e)
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            raise

    # ── Ingest ────────────────────────────────────────────────────────

    def ingest(self, payload: IngestPayload) -> Dict[str, int]:
        """存储 Video / Entity 节点和关系到 Memgraph。返回统计信息。"""
        if not self.available:
            logger.warning("GraphService.ingest: Memgraph not available, skipping")
            return {"entities_stored": 0, "relations_stored": 0}

        video = payload.video
        entities = payload.entities
        relations = payload.relations

        entities_stored = 0
        relations_stored = 0

        try:
            # 1) MERGE Video 节点（含第三波新增的存储路径字段）
            self._execute_write(
                """
                MERGE (v:Video {url: $url})
                SET v.title = $title,
                    v.platform = $platform,
                    v.video_id = $video_id,
                    v.channel = $channel,
                    v.duration = $duration,
                    v.description = $description,
                    v.published_at = $published_at,
                    v.audio_storage_id = $audio_storage_id,
                    v.audio_storage_path = $audio_storage_path,
                    v.transcript_storage_id = $transcript_storage_id
                """,
                {
                    "url": video.url,
                    "title": video.title,
                    "platform": video.platform.value,
                    "video_id": video.video_id,
                    "channel": video.channel,
                    "duration": video.duration,
                    "description": video.description,
                    "published_at": video.published_at or "",
                    "audio_storage_id": payload.audio_storage_id or "",
                    "audio_storage_path": payload.audio_storage_path or "",
                    "transcript_storage_id": payload.transcript_storage_id or "",
                },
            )

            # 2) MERGE Entity 节点 + MENTIONED_IN 关系
            for ent in entities:
                self._execute_write(
                    """
                    MERGE (e:Entity {name: $name})
                    SET e.type = $type,
                        e.description = $description,
                        e.confidence = $confidence
                    WITH e
                    MATCH (v:Video {url: $url})
                    MERGE (e)-[r:MENTIONED_IN]->(v)
                    """,
                    {
                        "name": ent.name,
                        "type": ent.type,
                        "description": ent.description,
                        "confidence": ent.confidence,
                        "url": video.url,
                    },
                )
                entities_stored += 1

            # 3) MERGE 关系边
            for rel in relations:
                self._execute_write(
                    """
                    MERGE (e1:Entity {name: $source})
                    MERGE (e2:Entity {name: $target})
                    MERGE (e1)-[r:RELATED_TO]->(e2)
                    SET r.relation = $relation,
                        r.description = $description,
                        r.confidence = $confidence,
                        r.video_url = $url
                    """,
                    {
                        "source": rel.source,
                        "target": rel.target,
                        "relation": rel.relation,
                        "description": rel.description,
                        "confidence": rel.confidence,
                        "url": video.url,
                    },
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
        """查询实体及其所有关联关系"""
        if not self.available:
            return [{"error": "graph_unavailable", "message": "Graph DB is not connected"}]

        try:
            results = self._execute(
                """
                MATCH (e:Entity {name: $name})-[r]-(other)
                RETURN e.name AS source,
                       other.name AS target,
                       type(r) AS relation_type,
                       labels(other) AS target_labels
                """,
                {"name": name},
            )
            return results
        except Exception as e:
            logger.error("query_entity error: %s", e)
            return [{"error": "query_failed", "message": str(e)}]

    def query_video(self, url: str) -> List[Dict[str, Any]]:
        """查询视频的所有关联实体"""
        if not self.available:
            return [{"error": "graph_unavailable", "message": "Graph DB is not connected"}]

        try:
            results = self._execute(
                """
                MATCH (e:Entity)-[r:MENTIONED_IN]->(v:Video {url: $url})
                RETURN e.name AS name, e.type AS type, e.description AS description, e.confidence AS confidence
                """,
                {"url": url},
            )
            return results
        except Exception as e:
            logger.error("query_video error: %s", e)
            return [{"error": "query_failed", "message": str(e)}]

    def query_subgraph(self, entity: str, depth: int = 2) -> Dict[str, Any]:
        """子图遍历：从指定实体出发，遍历指定深度"""
        if not self.available:
            return {"error": "graph_unavailable", "message": "Graph DB is not connected"}

        depth = min(depth, 5)
        try:
            # Memgraph 不支持 [*1..N] 可变长度路径中带变量的 limit，
            # 改为固定深度展开
            results = self._execute(
                f"""
                MATCH path = (e:Entity {{name: $name}})-[*1..{depth}]-(other:Entity)
                WITH nodes(path) AS ns, relationships(path) AS rs
                UNWIND ns AS n
                WITH COLLECT(DISTINCT {{name: n.properties.name, type: n.properties.type, labels: labels(n)}}) AS nodes, rs
                UNWIND rs AS r
                WITH nodes, COLLECT(DISTINCT {{
                    source: startNode(r).properties.name,
                    target: endNode(r).properties.name,
                    relation: type(r)
                }}) AS edges
                RETURN nodes, edges
                """,
                {"name": entity},
            )
            if results:
                return results[0]
            return {"nodes": [], "edges": []}
        except Exception as e:
            logger.error("query_subgraph error: %s", e)
            return {"error": "query_failed", "message": str(e), "nodes": [], "edges": []}


def _parse_host(uri: str) -> str:
    """从 bolt://host:port 提取 host"""
    import re
    match = re.match(r"(?:bolt|neo4j)://([^:]+)(?::(\d+))?", uri)
    return match.group(1) if match else "localhost"


def _parse_port(uri: str) -> int:
    """从 bolt://host:port 提取 port"""
    import re
    match = re.match(r"(?:bolt|neo4j)://[^:]+:(\d+)", uri)
    return int(match.group(1)) if match else 7687
