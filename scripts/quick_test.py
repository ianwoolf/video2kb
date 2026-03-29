"""
快速测试脚本 - 不需要下载视频，用模拟数据测试
"""
import sys
sys.path.insert(0, '/data/research/video-analysis')

from entity_extractor import EntityExtractor
from knowledge_graph import KnowledgeGraph
from document_generator import DocumentGenerator

print("=== 视频分析Demo - 快速测试 ===\n")

# 模拟视频信息
video_info = {
    "platform": "youtube",
    "url": "https://www.youtube.com/watch?v=demo123",
    "title": "人工智能的发展历程",
    "duration": 1800,
    "description": "本视频讲述了人工智能从1950年代至今的发展历程"
}

# 模拟转录文本
transcript = """
1956年，约翰·麦卡锡在达特茅斯会议上首次提出人工智能的概念。
艾伦·图灵在1950年发表了著名的图灵测试论文。
1980年代，专家系统开始兴起，日本启动了第五代计算机项目。
2012年，AlexNet在ImageNet竞赛中取得突破，深度学习时代开启。
2017年，Google Brain团队提出了Transformer架构。
2022年，ChatGPT发布，大语言模型进入大众视野。
在中国，清华大学、北京大学、中科院等机构在AI领域做出了重要贡献。
中国计算机学会（CCF）设立了人工智能专业委员会。
"""

print(f"1. 视频信息:")
print(f"   标题: {video_info['title']}")
print(f"   时长: {video_info['duration']}秒\n")

# 测试实体提取
print("2. 测试实体提取...")
extractor = EntityExtractor(use_llm=False)
result = extractor.extract(transcript)
print(f"   识别到 {result['entity_count']} 个实体:")

for entity in result["entities"][:10]:
    print(f"   - {entity.text} ({entity.label})")

print()

# 测试知识图谱
print("3. 测试知识图谱构建...")
kg = KnowledgeGraph(db_type="networkx")

kg.add_video(video_info["url"], video_info["title"], video_info["duration"])

for entity in result["entities"]:
    kg.add_entity(entity, video_info["url"])

print("   知识图谱构建完成")
print()

# 测试查询
print("4. 测试图谱查询...")
if result["entities"]:
    sample_entity = result["entities"][0].text
    query_results = kg.query_entity(sample_entity)
    print(f"   查询 '{sample_entity}' 的关系:")
    for rel in query_results:
        print(f"   - {rel}")

print()

# 测试文档生成
print("5. 测试文档生成...")
doc_gen = DocumentGenerator(output_format="markdown")

analysis = {
    "transcript": transcript,
    "summary": doc_gen.generate_summary(transcript),
    "entities": [
        {"text": e.text, "label": e.label}
        for e in result["entities"]
    ],
    "relations": []
}

doc_path = doc_gen.generate(video_info, analysis)
print(f"   文档生成成功: {doc_path}")

# 读取生成的文档
with open(doc_path, "r", encoding="utf-8") as f:
    content = f.read()
    print(f"\n   文档预览:")
    print("   " + "\n   ".join(content.split("\n")[:15]))
    print("   ...")

print("\n=== 测试完成 ===")
print(f"✓ 实体提取: {result['entity_count']} 个实体")
print(f"✓ 知识图谱: {len(kg.graph.nodes)} 个节点")
print(f"✓ 文档生成: {doc_path}")
