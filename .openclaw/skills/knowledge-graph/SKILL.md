---
name: knowledge-graph
description: Store entities and relations in a knowledge graph (Neo4j/NetworkX) with query support
metadata:
  openclaw:
    requires:
      bins: [python3]
    optional:
      env: [NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]
---

# knowledge-graph

Store entities and relations in a knowledge graph, supporting both Neo4j and NetworkX backends. Provides entity queries, video entity queries, and timeline queries.

## Scripts

### graph_store.py — Storage

```bash
# NetworkX mode (default, no database required)
python3 scripts/graph_store.py \
  --video-info '{"url":"https://...","title":"test"}' \
  --entities '[{"text":"Zhang San","label":"PERSON","start":0,"end":2}]' \
  --db-type networkx

# Read data from files
python3 scripts/graph_store.py \
  --video-info-file video.json \
  --entities-file entities.json \
  --relations-file relations.json \
  --db-type networkx

# Neo4j mode
python3 scripts/graph_store.py \
  --video-info-file video.json \
  --entities-file entities.json \
  --db-type neo4j
```

### graph_query.py — Queries

```bash
# Query all relations for an entity
python3 scripts/graph_query.py --query-type entity --entity-name "Zhang San"

# Query all entities in a video
python3 scripts/graph_query.py --query-type video_entities --video-url "https://..."

# Query entity timeline in a video
python3 scripts/graph_query.py --query-type timeline --entity-name "Zhang San" --video-url "https://..."
```

## graph_store.py Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--video-info` | One of two | Video info JSON string |
| `--video-info-file` | One of two | Video info JSON file path |
| `--entities` | No | Entity list JSON string |
| `--entities-file` | No | Entity list JSON file path |
| `--relations` | No | Relation list JSON string |
| `--relations-file` | No | Relation list JSON file path |
| `--db-type` | No | networkx/neo4j (default: networkx) |
| `--graph-path` | No | NetworkX persistence path (default: data/graph_state.gpickle) |

## graph_query.py Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--query-type` | Yes | entity/video_entities/timeline |
| `--entity-name` | Conditional | Entity name (required for entity/timeline) |
| `--video-url` | Conditional | Video URL (required for video_entities/timeline) |
| `--db-type` | No | networkx/neo4j (default: networkx) |
| `--graph-path` | No | NetworkX persistence path |

## Output Format

Store output (success):
```json
{"nodes_added": 5, "edges_added": 8}
```

Store output (Neo4j unavailable):
```json
{
  "error": "neo4j_unavailable",
  "error_message": "Cannot connect to Neo4j at bolt://localhost:7687",
  "fix_hint": "Start Neo4j with:\n  docker-compose up -d\nOr set GRAPH_DB_TYPE=networkx to use local mode",
  "nodes_added": 0,
  "edges_added": 0
}
```

Query output (Neo4j unavailable):
```json
[{
  "error": "neo4j_unavailable",
  "error_message": "Cannot connect to Neo4j at bolt://localhost:7687",
  "fix_hint": "Start Neo4j with:\n  docker-compose up -d\nOr set --db-type networkx to use local mode"
}]
```

Query output (success): JSON array

## NetworkX Persistence

NetworkX mode serializes the graph to `data/graph_state.gpickle`. Each store operation appends to the existing graph.

## Error Handling

When `--db-type neo4j` is specified but Neo4j is not available:

- **Connection failed**: Returns error with hint to start Neo4j or use NetworkX
- **Authentication failed**: Returns error with hint to check credentials
- **Package not installed**: Returns error with hint to install neo4j package

The skill gracefully falls back by returning structured error information instead of crashing. The caller can decide whether to retry with NetworkX mode or abort.

## Related Documentation

- [Cypher Query Examples](references/cypher_examples.md)
