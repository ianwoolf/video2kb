# Neo4j Cypher Query Examples

## Basic Queries

### Query all video nodes
```cypher
MATCH (v:Video) RETURN v.title, v.url
```

### Query all relations for an entity
```cypher
MATCH (e:Entity {name: 'Zhang San'})-[r]->(other)
RETURN e.name, type(r), other
```

### Query all entities in a video
```cypher
MATCH (e:Entity)-[:MENTIONED_IN]->(v:Video {url: 'https://youtube.com/watch?v=xxx'})
RETURN e.name, e.type, e.confidence
```

## Advanced Queries

### Find the shortest path between two entities
```cypher
MATCH path = shortestPath((e1:Entity {name: 'Zhang San'})-[*..5]-(e2:Entity {name: 'Peking University'}))
RETURN path
```

### Find the most-mentioned entities across videos
```cypher
MATCH (e:Entity)-[r:MENTIONED_IN]->(v:Video)
RETURN e.name, e.type, count(v) AS mentions
ORDER BY mentions DESC
LIMIT 10
```

### Query entity timeline in a video
```cypher
MATCH (e:Entity {name: 'Zhang San'})-[r:MENTIONED_IN]->(v:Video {url: 'https://...'})
RETURN r.timestamp ORDER BY r.timestamp
```

### Find related entities via shared video mentions
```cypher
MATCH (e1:Entity {name: 'Zhang San'})-[:MENTIONED_IN]->(v:Video)<-[:MENTIONED_IN]-(e2:Entity)
WHERE e1 <> e2
RETURN e2.name, count(v) AS common_videos
ORDER BY common_videos DESC
LIMIT 10
```

### Query relations of a specific type
```cypher
MATCH (e1:Entity)-[r:RELATED_TO]->(e2:Entity)
WHERE r.relation = 'WORKS_AT'
RETURN e1.name, e2.name
```

## Data Model

```
(:Video {url, title, timestamp})
(:Entity {name, type, confidence})
(:Segment {id, text, start, end, video_url})

(:Entity)-[:MENTIONED_IN {timestamp}]->(:Video)
(:Entity)-[:RELATED_TO {relation, video_url, timestamp, context}]->(:Entity)
(:Segment)-[:BELONGS_TO]->(:Video)
```
