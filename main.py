"""
主程序 - 视频/图谱分析Pipeline
"""
import logging
import argparse
from pathlib import Path
from typing import Optional

from video_extractor import VideoExtractor
from transcriber import Transcriber
from entity_extractor import EntityExtractor
from knowledge_graph import KnowledgeGraph, GraphDBType
from document_generator import DocumentGenerator

from config import GRAPH_DB_TYPE

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VideoAnalysisPipeline:
    """视频分析Pipeline"""

    def __init__(self, graph_db_type: str = GRAPH_DB_TYPE):
        self.video_extractor = VideoExtractor()
        self.transcriber = None  # 延迟加载
        self.entity_extractor = EntityExtractor(use_llm=True)
        self.knowledge_graph = KnowledgeGraph(db_type=graph_db_type)
        self.document_generator = DocumentGenerator(output_format="markdown")

    def analyze(self, video_url: str, download_audio: bool = True) -> dict:
        """
        完整分析流程

        Args:
            video_url: 视频URL
            download_audio: 是否下载音频（用于ASR）

        Returns:
            分析结果字典
        """
        logger.info(f"Starting analysis for: {video_url}")

        # 1. 提取视频信息
        logger.info("Step 1: Extracting video info...")
        video_info = self.video_extractor.extract(video_url, download_audio=download_audio)

        # 2. 如果没有字幕，使用ASR
        transcript = video_info.get("transcript", "")
        if not transcript and download_audio:
            audio_path = video_info.get("audio_path", "")
            if audio_path:
                logger.info("Step 2: Transcribing audio with Whisper...")
                transcriber = Transcriber()
                transcript_result = transcriber.transcribe_file(audio_path)
                transcript = transcript_result["text"]
                video_info["transcript"] = transcript

        if not transcript:
            logger.warning("No transcript available!")
            return {"error": "No transcript available"}

        # 3. 提取实体和关系
        logger.info("Step 3: Extracting entities and relations...")
        entity_result = self.entity_extractor.extract(transcript, video_url)

        # 4. 构建知识图谱
        logger.info("Step 4: Building knowledge graph...")
        self._build_graph(video_info, entity_result)

        # 5. 生成文档
        logger.info("Step 5: Generating document...")
        analysis = {
            "transcript": transcript,
            "summary": self.document_generator.generate_summary(transcript),
            "entities": [
                {"text": e.text, "label": e.label}
                for e in entity_result["entities"]
            ],
            "relations": [
                {
                    "source": r.source,
                    "target": r.target,
                    "relation": r.relation,
                    "timestamp": r.timestamp
                }
                for r in entity_result["relations"]
            ],
            "timeline": self._extract_timeline(entity_result["entities"])
        }

        doc_path = self.document_generator.generate(video_info, analysis)

        # 6. 查询图谱（示例）
        if entity_result["entities"]:
            sample_entity = entity_result["entities"][0].text
            graph_results = self.knowledge_graph.query_entity(sample_entity)
            logger.info(f"Graph query for '{sample_entity}': {len(graph_results)} results")

        result = {
            "video_info": video_info,
            "analysis": analysis,
            "document_path": doc_path,
            "entity_count": len(entity_result["entities"]),
            "relation_count": len(entity_result["relations"])
        }

        logger.info(f"Analysis complete! Document: {doc_path}")
        return result

    def _build_graph(self, video_info: dict, entity_result: dict):
        """构建知识图谱"""
        video_url = video_info["url"]
        title = video_info.get("title", "")
        duration = video_info.get("duration", 0)

        # 添加视频节点
        self.knowledge_graph.add_video(video_url, title, duration)

        # 添加实体
        for entity in entity_result["entities"]:
            self.knowledge_graph.add_entity(entity, video_url)

        # 添加关系
        for relation in entity_result["relations"]:
            self.knowledge_graph.add_relation(relation, video_url)

    def _extract_timeline(self, entities: list) -> list:
        """提取实体时间线"""
        timeline = []
        for entity in entities:
            if entity.start > 0:
                timeline.append({
                    "timestamp": entity.start,
                    "text": entity.text
                })

        return sorted(timeline, key=lambda x: x["timestamp"])

    def batch_analyze(self, url_file: str) -> list:
        """批量分析视频"""
        url_file_path = Path(url_file)
        if not url_file_path.exists():
            raise FileNotFoundError(f"URL file not found: {url_file}")

        with open(url_file_path, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]

        results = []
        for i, url in enumerate(urls, 1):
            logger.info(f"Processing {i}/{len(urls)}: {url}")
            try:
                result = self.analyze(url)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process {url}: {e}")
                results.append({"url": url, "error": str(e)})

        return results

    def query(self, entity_name: str) -> list:
        """查询知识图谱"""
        return self.knowledge_graph.query_entity(entity_name)

    def close(self):
        """清理资源"""
        if hasattr(self.knowledge_graph, "close"):
            self.knowledge_graph.close()


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="视频内容分析与知识图谱构建")
    parser.add_argument("--url", help="单个视频URL")
    parser.add_argument("--batch", help="批量处理（包含URL列表的文件）")
    parser.add_argument("--no-audio", action="store_true", help="不下载音频（假设已有字幕）")
    parser.add_argument("--graph", choices=["neo4j", "networkx"],
                       default=GRAPH_DB_TYPE, help="图数据库类型")
    parser.add_argument("--query", help="查询知识图谱中的实体")

    args = parser.parse_args()

    pipeline = VideoAnalysisPipeline(graph_db_type=args.graph)

    try:
        if args.query:
            # 查询模式
            results = pipeline.query(args.query)
            print(f"Query results for '{args.query}':")
            for result in results:
                print(f"  - {result}")
        elif args.url:
            # 单个视频
            result = pipeline.analyze(args.url, download_audio=not args.no_audio)
            if "error" in result:
                print(f"\n分析失败: {result['error']}")
            else:
                print(f"\n分析完成！")
                print(f"文档路径: {result['document_path']}")
                print(f"实体数量: {result['entity_count']}")
                print(f"关系数量: {result['relation_count']}")
        elif args.batch:
            # 批量处理
            results = pipeline.batch_analyze(args.batch)
            print(f"\n批量处理完成！共处理 {len(results)} 个视频")
            for i, result in enumerate(results, 1):
                if "error" in result:
                    print(f"{i}. 失败: {result['url']}")
                else:
                    print(f"{i}. 成功: {result['document_path']}")
        else:
            parser.print_help()
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
