#!/usr/bin/env python3
"""
Knowledge Graph Storage - Store entities and relations in Neo4j or NetworkX

Usage:
    python3 graph_store.py --video-info 'JSON' --entities 'JSON' --relations 'JSON' [--db-type networkx]
    python3 graph_store.py --video-info-file video.json --entities-file entities.json [--db-type neo4j]
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


def _load_json_arg(value: str, file_value: str = None):
    if file_value:
        return json.loads(Path(file_value).read_text(encoding="utf-8"))
    return json.loads(value)


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
                f"Or set GRAPH_DB_TYPE=networkx to use local mode"
            )
        elif "authentication" in error_msg.lower():
            return False, f"Neo4j authentication failed: {error_msg}", (
                f"Check your NEO4J_USER and NEO4J_PASSWORD in .env file.\n"
                f"Default: NEO4J_USER=neo4j, NEO4J_PASSWORD=password"
            )
        else:
            return False, f"Neo4j error: {error_msg}", "Check Neo4j logs for details"


def _load_graph(db_type: str, graph_path: str):
    """Load an existing graph (NetworkX: restore from file; Neo4j: connect to database)"""
    if db_type == "networkx":
        import networkx as nx
        p = Path(graph_path)
        if p.exists():
            graph = pickle.loads(p.read_bytes())
            logger.info("Loaded existing NetworkX graph: %d nodes, %d edges", graph.number_of_nodes(), graph.number_of_edges())
        else:
            graph = nx.MultiDiGraph()
            logger.info("Created new NetworkX graph")
        return graph
    else:
        return _init_neo4j()


def _save_graph(graph, graph_path: str):
    """Persist NetworkX graph to disk"""
    p = Path(graph_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(pickle.dumps(graph))
    logger.info("Saved NetworkX graph to: %s", graph_path)


def _init_neo4j():
    from neo4j import GraphDatabase
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        session.run("RETURN 1")
    logger.info("Connected to Neo4j: %s", uri)
    return driver


def _neo4j_add_video(driver, url, title, duration):
    with driver.session() as session:
        session.run("MERGE (v:Video {url: $url}) SET v.title = $title, v.timestamp = $duration", url=url, title=title, duration=duration)


def _neo4j_add_entity(driver, entity, video_url):
    with driver.session() as session:
        session.run(
            "MERGE (e:Entity {name: $name}) SET e.type = $type, e.confidence = $confidence "
            "MERGE (v:Video {url: $video_url}) "
            "MERGE (e)-[r:MENTIONED_IN]->(v) SET r.timestamp = $timestamp",
            name=entity["text"], type=entity["label"], confidence=entity.get("confidence", 1.0),
            video_url=video_url, timestamp=entity.get("start", 0),
        )


def _neo4j_add_relation(driver, relation, video_url):
    with driver.session() as session:
        session.run(
            "MERGE (e1:Entity {name: $source}) MERGE (e2:Entity {name: $target}) "
            "MERGE (e1)-[r:RELATED_TO]->(e2) "
            "SET r.relation = $relation, r.video_url = $video_url, r.timestamp = $timestamp, r.context = $context",
            source=relation["source"], target=relation["target"],
            relation=relation.get("relation", ""), video_url=video_url,
            timestamp=relation.get("timestamp"), context=relation.get("context", ""),
        )


def store(video_info: dict, entities: list, relations: list, db_type: str = "networkx", graph_path: str = DEFAULT_GRAPH_PATH) -> dict:
    # Check Neo4j availability if requested
    if db_type == "neo4j":
        available, error_msg, fix_hint = _check_neo4j_available()
        if not available:
            logger.error("Neo4j not available: %s", error_msg)
            logger.info("To fix this:\n%s", fix_hint)
            return {
                "error": "neo4j_unavailable",
                "error_message": error_msg,
                "fix_hint": fix_hint,
                "nodes_added": 0,
                "edges_added": 0
            }

    nodes_added = 0
    edges_added = 0
    video_url = video_info.get("url", "")
    title = video_info.get("title", "")
    duration = video_info.get("duration", 0)

    if db_type == "networkx":
        import networkx as nx
        graph = _load_graph(db_type, graph_path)

        # Add video node
        graph.add_node(video_url, type="Video", title=title, timestamp=duration)
        nodes_added += 1

        # Add entity nodes and edges
        for entity in entities:
            text = entity.get("text", "")
            if text:
                graph.add_node(text, type=entity.get("label", "Entity"), confidence=entity.get("confidence", 1.0))
                graph.add_edge(text, video_url, relation="MENTIONED_IN", timestamp=entity.get("start", 0))
                nodes_added += 1
                edges_added += 1

        # Add relation edges
        for rel in relations:
            source = rel.get("source", "")
            target = rel.get("target", "")
            if source and target:
                graph.add_edge(
                    source, target,
                    relation=rel.get("relation", ""),
                    video_url=video_url,
                    timestamp=rel.get("timestamp"),
                    context=rel.get("context", ""),
                    confidence=rel.get("confidence", 1.0),
                )
                edges_added += 1

        _save_graph(graph, graph_path)

    elif db_type == "neo4j":
        driver = _load_graph(db_type, graph_path)
        try:
            _neo4j_add_video(driver, video_url, title, duration)
            nodes_added += 1
            for entity in entities:
                _neo4j_add_entity(driver, entity, video_url)
                nodes_added += 1
                edges_added += 1
            for rel in relations:
                _neo4j_add_relation(driver, rel, video_url)
                edges_added += 1
        finally:
            driver.close()

    result = {"nodes_added": nodes_added, "edges_added": edges_added}
    logger.info("Stored %d nodes, %d edges", nodes_added, edges_added)
    return result


def main():
    parser = argparse.ArgumentParser(description="Store entities and relations in a knowledge graph (Neo4j/NetworkX)")
    parser.add_argument("--video-info", help="Video info JSON string")
    parser.add_argument("--video-info-file", help="Video info JSON file path")
    parser.add_argument("--entities", help="Entity list JSON string")
    parser.add_argument("--entities-file", help="Entity list JSON file path")
    parser.add_argument("--relations", default="[]", help="Relation list JSON string (default: [])")
    parser.add_argument("--relations-file", help="Relation list JSON file path")
    parser.add_argument("--db-type", choices=["networkx", "neo4j"], default="networkx", help="Graph database type (default: networkx)")
    parser.add_argument("--graph-path", default=DEFAULT_GRAPH_PATH, help="NetworkX graph persistence path (default: data/graph_state.gpickle)")
    args = parser.parse_args()

    video_info = _load_json_arg(args.video_info or "{}", args.video_info_file)
    entities = _load_json_arg(args.entities or "[]", args.entities_file)
    relations = _load_json_arg(args.relations or "[]", args.relations_file)

    result = store(video_info, entities, relations, db_type=args.db_type, graph_path=args.graph_path)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
