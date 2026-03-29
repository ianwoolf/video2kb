# Neo4j Docker Compose Setup

## Quick Start

### 1. Start the Neo4j Container

```bash
cd /data/research/video-analysis
docker-compose up -d
```

### 2. Wait for Neo4j to Start (about 30-60 seconds)

```bash
# View logs
docker-compose logs -f neo4j

# Wait until you see log entries similar to:
# Remote interface available at http://localhost:7474/
# Bolt enabled on 0.0.0.0:7687
```

### 3. Test the Connection

Open a browser and visit:
- **UI Interface**: http://localhost:7474
- **Username**: neo4j
- **Password**: password

Or test via the command line:
```bash
curl -u neo4j:password http://localhost:7474
```

---

## Using with the Video Analysis Project

Once Neo4j is running, run the analysis:

```bash
# Use Neo4j graph database
python main.py --url "your_bilibili_link" --graph neo4j

# Or set GRAPH_DB_TYPE to "neo4j" in config.py
```

---

## Common Commands

### View Status
```bash
docker-compose ps
```

### View Logs
```bash
docker-compose logs -f neo4j
```

### Stop the Container
```bash
docker-compose down
```

### Full Cleanup (delete data)
```bash
docker-compose down -v
```

### Restart the Container
```bash
docker-compose restart
```

---

## Configuration Details

### Port Mapping
| Container Port | Host Port | Purpose |
|----------|----------|------|
| 7474     | 7474     | HTTP UI (browser access) |
| 7687     | 7687     | Bolt protocol (program connection) |

### Environment Variables
- `NEO4J_AUTH`: Username and password (neo4j/password)
- `NEO4J_PLUGINS`: Enabled plugins (APOC)
- `NEO4J_dbms_memory_*`: Memory configuration

### Data Persistence
Data is stored in Docker volumes:
- `neo4j_data`: Database data
- `neo4j_logs`: Log files
- `neo4j_import`: Import files
- `neo4j_plugins`: Plugin directory

---

## Troubleshooting

### Container Fails to Start
```bash
# Check if the port is already in use
netstat -tuln | grep 7687

# Or
lsof -i :7687
```

### Connection Failure
```bash
# Check if Neo4j is ready
docker-compose logs neo4j | grep "started"

# Test Bolt connection
nc -zv localhost 7687
```

### Insufficient Memory
Modify the memory configuration in `docker-compose.yml`:
```yaml
environment:
  - NEO4J_dbms_memory_pagecache_size=512M  # Reduce to 512M
  - NEO4J_dbms_memory_heap_max__size=256M   # Reduce to 256M
```

---

## Neo4j UI Usage

1. Open http://localhost:7474
2. Log in (neo4j/password)
3. Execute queries in the Cypher Shell:

```cypher
// View all nodes
MATCH (n) RETURN n LIMIT 25

// View all relationships
MATCH ()-[r]->() RETURN r LIMIT 25

// Count nodes
MATCH (n) RETURN count(n)

// Clear the database (use with caution!)
MATCH (n) DETACH DELETE n
```

---

## Configuration File

Ensure the settings in `config.py` match docker-compose.yml:

```python
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"
GRAPH_DB_TYPE = "neo4j"
```
