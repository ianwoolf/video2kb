#!/usr/bin/env python3
"""
Knowledge Graph Query - Query entities and relations in Neo4j or NetworkX

Usage:
    python3 graph_query.py --query-type entity --entity-name "EntityName" [--db-type networkx]
    python3 graph_query.py --query-type video_entities --video-url "https://..."
    python3 graph_query.py --query-type timeline --entity-name "EntityName" --video-url "https://..."
"""
import argparse
import json
import logging
import os
import pickle
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

DEFAULT_GRAPH_PATH = "data/graph_state.gpickle"


def _check_neo4j_available():
    """Check if Neo4j is available. Returns (is_available, error_message, fix_hint)"""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        return False, "neo4j Python package is not installed", "Install with: pip install neo4j"

    # Try to connect
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run("RETURN 1")
        driver.close()
        return True, None, None
    except Exception as e:
        driver.close()
        error_msg = str(e)
        if "connect" in error_msg.lower() or "connection" in error_msg.lower() or "failed" in error_msg.lower():
            return False, f"Cannot connect to Neo4j at {uri}", (
                f"Start Neo4j with:\n"
                f"  docker-compose up -d\n"
                f"Or set --db-type networkx to use local mode"
            )
        elif "authentication" in error_msg.lower():
            return False, f"Neo4j authentication failed: {error_msg}", (
                f"Check your NEO4J_USER and NEO4J_PASSWORD in .env file.\n"
                f"Default: NEO4J_USER=neo4j, NEO4J_PASSWORD=password"
            )
        else:
            return False, f"Neo4j error: {error_msg}", "Check Neo4j logs for details"


def _init_neo4j():
    from neo4j import GraphDatabase
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        session.run("RETURN 1")
    return driver


def query_entity(entity_name: str, db_type: str = "networkx", graph_path: str = DEFAULT_GRAPH_PATH) -> list:
    if db_type == "networkx":
        import networkx as nx
        p = Path(graph_path)
        if not p.exists():
            return []
        graph = pickle.loads(p.read_bytes())
        if entity_name not in graph:
            return []
        results = []
        for neighbor, edge_data in graph[entity_name].items():
            results.append({"entity": neighbor, "relation": edge_data.get("relation", "CONNECTED"), **edge_data})
        return results
    else:
        available, error_msg, fix_hint = _check_neo4j_available()
        if not available:
            logger.error("Neo4j not available: %s", error_msg)
            logger.info("To fix this:\n%s", fix_hint)
            return [{"error": "neo4j_unavailable", "error_message": error_msg, "fix_hint": fix_hint}]

        driver = _init_neo4j()
        try:
            with driver.session() as session:
                result = session.run(
                    "MATCH (e:Entity {name: $name})-[r]->(other) RETURN e, r, other",
                    name=entity_name,
                )
                return [record.data() for record in result]
        finally:
            driver.close()


def query_video_entities(video_url: str, db_type: str = "networkx", graph_path: str = DEFAULT_GRAPH_PATH) -> list:
    if db_type == "networkx":
        import networkx as nx
        p = Path(graph_path)
        if not p.exists():
            return []
        graph = pickle.loads(p.read_bytes())
        if video_url not in graph:
            return []
        entities = []
        for predecessor in graph.predecessors(video_url):
            node_data = dict(graph.nodes[predecessor])
            node_data["name"] = predecessor
            entities.append(node_data)
        return entities
    else:
        available, error_msg, fix_hint = _check_neo4j_available()
        if not available:
            logger.error("Neo4j not available: %s", error_msg)
            logger.info("To fix this:\n%s", fix_hint)
            return [{"error": "neo4j_unavailable", "error_message": error_msg, "fix_hint": fix_hint}]

        driver = _init_neo4j()
        try:
            with driver.session() as session:
                result = session.run(
                    "MATCH (e:Entity)-[:MENTIONED_IN]->(v:Video {url: $url}) RETURN e.name, e.type, e.confidence",
                    url=video_url,
                )
                return [record.data() for record in result]
        finally:
            driver.close()


def query_timeline(video_url: str, entity_name: str, db_type: str = "networkx", graph_path: str = DEFAULT_GRAPH_PATH) -> list:
    if db_type == "networkx":
        import networkx as nx
        p = Path(graph_path)
        if not p.exists():
            return []
        graph = pickle.loads(p.read_bytes())
        if entity_name not in graph or video_url not in graph[entity_name]:
            return []
        edges = graph[entity_name][video_url]
        timestamps = []
        for key, data in edges.items():
            ts = data.get("timestamp", 0)
            timestamps.append({"timestamp": ts, "entity": entity_name})
        return sorted(timestamps, key=lambda x: x["timestamp"])
    else:
        available, error_msg, fix_hint = _check_neo4j_available()
        if not available:
            logger.error("Neo4j not available: %s", error_msg)
            logger.info("To fix this:\n%s", fix_hint)
            return [{"error": "neo4j_unavailable", "error_message": error_msg, "fix_hint": fix_hint}]

        driver = _init_neo4j()
        try:
            with driver.session() as session:
                result = session.run(
                    "MATCH (e:Entity {name: $name})-[r:MENTIONED_IN]->(v:Video {url: $url}) "
                    "RETURN r.timestamp ORDER BY r.timestamp",
                    name=entity_name, url=video_url,
                )
                return [record.data() for record in result]
        finally:
            driver.close()


def main():
    parser = argparse.ArgumentParser(description="Query the knowledge graph (Neo4j/NetworkX)")
    parser.add_argument("--query-type", required=True, choices=["entity", "video_entities", "timeline"],
                        help="Query type: entity (entity relations), video_entities (video entities), timeline (entity timeline)")
    parser.add_argument("--entity-name", help="Entity name")
    parser.add_argument("--video-url", help="Video URL")
    parser.add_argument("--db-type", choices=["networkx", "neo4j"], default="networkx", help="Graph database type (default: networkx)")
    parser.add_argument("--graph-path", default=DEFAULT_GRAPH_PATH, help="NetworkX graph persistence path (default: data/graph_state.gpickle)")
    args = parser.parse_args()

    if args.query_type == "entity":
        if not args.entity_name:
            parser.error("--query-type entity requires --entity-name")
        result = query_entity(args.entity_name, args.db_type, args.graph_path)
    elif args.query_type == "video_entities":
        if not args.video_url:
            parser.error("--query-type video_entities requires --video-url")
        result = query_video_entities(args.video_url, args.db_type, args.graph_path)
    elif args.query_type == "timeline":
        if not args.entity_name or not args.video_url:
            parser.error("--query-type timeline requires both --entity-name and --video-url")
        result = query_timeline(args.video_url, args.entity_name, args.db_type, args.graph_path)

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
