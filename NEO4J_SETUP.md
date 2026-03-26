# Neo4j Docker Compose 设置

## 快速启动

### 1. 启动 Neo4j 容器

```bash
cd /data/research/video-analysis
docker-compose up -d
```

### 2. 等待 Neo4j 启动（约30-60秒）

```bash
# 查看日志
docker-compose logs -f neo4j

# 等到看到类似这样的日志：
# Remote interface available at http://localhost:7474/
# Bolt enabled on 0.0.0.0:7687
```

### 3. 测试连接

打开浏览器访问：
- **UI界面**: http://localhost:7474
- **用户名**: neo4j
- **密码**: password

或者用命令行测试：
```bash
curl -u neo4j:password http://localhost:7474
```

---

## 使用视频分析项目

确认 Neo4j 启动后，运行分析：

```bash
# 使用 Neo4j 图数据库
python main.py --url "你的B站链接" --graph neo4j

# 或者修改 config.py 中的 GRAPH_DB_TYPE 为 "neo4j"
```

---

## 常用命令

### 查看状态
```bash
docker-compose ps
```

### 查看日志
```bash
docker-compose logs -f neo4j
```

### 停止容器
```bash
docker-compose down
```

### 完全清理（删除数据）
```bash
docker-compose down -v
```

### 重启容器
```bash
docker-compose restart
```

---

## 配置说明

### 端口映射
| 容器端口 | 主机端口 | 用途 |
|----------|----------|------|
| 7474     | 7474     | HTTP UI（浏览器访问） |
| 7687     | 7687     | Bolt协议（程序连接） |

### 环境变量
- `NEO4J_AUTH`: 用户名和密码（neo4j/password）
- `NEO4J_PLUGINS`: 启用的插件（APOC）
- `NEO4J_dbms_memory_*`: 内存配置

### 数据持久化
数据存储在 Docker volumes 中：
- `neo4j_data`: 数据库数据
- `neo4j_logs`: 日志文件
- `neo4j_import`: 导入文件
- `neo4j_plugins`: 插件目录

---

## 故障排除

### 容器无法启动
```bash
# 检查端口是否被占用
netstat -tuln | grep 7687

# 或者
lsof -i :7687
```

### 连接失败
```bash
# 检查 Neo4j 是否就绪
docker-compose logs neo4j | grep "started"

# 测试 Bolt 连接
nc -zv localhost 7687
```

### 内存不足
修改 `docker-compose.yml` 中的内存配置：
```yaml
environment:
  - NEO4J_dbms_memory_pagecache_size=512M  # 减少到512M
  - NEO4J_dbms_memory_heap_max__size=256M   # 减少到256M
```

---

## Neo4j UI 使用

1. 打开 http://localhost:7474
2. 登录（neo4j/password）
3. 在 Cypher Shell 中执行查询：

```cypher
// 查看所有节点
MATCH (n) RETURN n LIMIT 25

// 查看所有关系
MATCH ()-[r]->() RETURN r LIMIT 25

// 统计节点数量
MATCH (n) RETURN count(n)

// 清空数据库（慎用！）
MATCH (n) DETACH DELETE n
```

---

## 配置文件

确保 `config.py` 中的配置与 docker-compose.yml 匹配：

```python
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"
GRAPH_DB_TYPE = "neo4j"
```
