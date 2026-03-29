#!/usr/bin/env python3
"""
Full Pipeline Runner - Invoke standalone scripts to run the complete video analysis workflow

Usage:
    python3 run_pipeline.py --url "https://youtube.com/watch?v=xxx"
    python3 run_pipeline.py --url "https://bilibili.com/video/BVxxx" --graph neo4j
    python3 run_pipeline.py --batch urls.txt --format markdown
"""
import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).parent


def run_script(script_name: str, args: list) -> dict:
    """Run a sub-script and parse its JSON output"""
    script_path = SCRIPTS_DIR / script_name
    cmd = [sys.executable, str(script_path)] + args
    logger.info("Running: %s", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("Script %s failed: %s", script_name, result.stderr)
        raise RuntimeError(f"Script {script_name} failed: {result.stderr}")

    # Log stderr in case there's useful info (but don't fail on it)
    if result.stderr.strip():
        logger.debug("Stderr from %s: %s", script_name, result.stderr.strip())

    output = result.stdout.strip()
    if not output:
        return {}

    try:
        return json.loads(output)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON from %s: %s", script_name, e)
        logger.error("Raw output was: %s", output[:500])
        raise


def analyze(url: str, graph: str = "networkx", fmt: str = "markdown", use_llm: bool = False) -> dict:
    logger.info("=== Starting pipeline for: %s ===", url)

    # Step 1: Video extraction (auto-detects if audio download is needed)
    logger.info("[1/6] Extracting video info...")
    extract_args = ["--url", url, "--output-dir", "data/raw"]
    video_info = run_script("extract_video.py", extract_args)

    transcript = video_info.get("transcript", "")
    audio_path = video_info.get("audio_path", "")

    # Step 2: If no subtitles, use ASR
    if not transcript and audio_path:
        logger.info("[2/6] Transcribing audio...")
        transcript_result = run_script("transcribe.py", [
            "--audio", audio_path,
            "--output-dir", "data/transcripts",
        ])
        transcript = transcript_result.get("text", "")
        video_info["transcript"] = transcript
    else:
        if transcript:
            logger.info("[2/6] Using extracted subtitle (skipping ASR)")
        else:
            logger.info("[2/6] No audio or subtitle available")

    if not transcript:
        logger.error("No transcript available, cannot continue")
        return {"error": "No transcript available", "video_info": video_info}

    # Step 3: Text summarization
    logger.info("[3/6] Summarizing text...")
    # Save transcript to a temporary file
    tmp_text = Path("data/transcripts/_pipeline_tmp.txt")
    tmp_text.parent.mkdir(parents=True, exist_ok=True)
    tmp_text.write_text(transcript, encoding="utf-8")

    summary_result = run_script("summarize.py", [
        "--input-file", str(tmp_text),
        "--output-dir", "data/docs",
    ])

    # Step 4: Entity extraction
    logger.info("[4/6] Extracting entities...")
    entity_args = ["--input-file", str(tmp_text), "--source-url", url]
    if use_llm:
        entity_args.append("--use-llm")
    entity_result = run_script("extract_entities.py", entity_args)

    # Step 5: Knowledge graph storage
    logger.info("[5/6] Storing to knowledge graph...")
    video_info_json = json.dumps(video_info, ensure_ascii=False)
    entities_json = json.dumps(entity_result.get("entities", []), ensure_ascii=False)
    relations_json = json.dumps(entity_result.get("relations", []), ensure_ascii=False)

    graph_result = run_script("graph_store.py", [
        "--video-info", video_info_json,
        "--entities", entities_json,
        "--relations", relations_json,
        "--db-type", graph,
    ])

    # Check for Neo4j errors
    if "error" in graph_result and graph_result.get("error") == "neo4j_unavailable":
        logger.warning("Neo4j unavailable, results not stored to graph database")
        logger.info("Hint: %s", graph_result.get("fix_hint", ""))

    # Step 6: Report generation
    logger.info("[6/6] Generating report...")
    analysis = {
        "transcript": transcript,
        "summary": summary_result.get("summary", ""),
        "key_points": summary_result.get("key_points", []),
        "entities": entity_result.get("entities", []),
        "relations": entity_result.get("relations", []),
        "timeline": _extract_timeline(entity_result.get("entities", [])),
    }

    # Save intermediate results
    analysis_path = Path("data/docs/_pipeline_analysis.json")
    analysis_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    video_info_path = Path("data/docs/_pipeline_video_info.json")
    video_info_path.write_text(json.dumps(video_info, ensure_ascii=False, indent=2), encoding="utf-8")

    report_result = run_script("generate_report.py", [
        "--video-info-file", str(video_info_path),
        "--analysis-file", str(analysis_path),
        "--format", fmt,
        "--output-dir", "data/docs",
    ])

    # Clean up temporary file
    tmp_text.unlink(missing_ok=True)

    final_result = {
        "video_info": video_info,
        "summary": summary_result.get("summary", ""),
        "key_points": summary_result.get("key_points", []),
        "entity_count": len(entity_result.get("entities", [])),
        "relation_count": len(entity_result.get("relations", [])),
        "graph_nodes_added": graph_result.get("nodes_added", 0),
        "document_path": report_result.get("document_path", ""),
        "document_format": report_result.get("format", fmt),
    }

    logger.info("=== Pipeline complete! ===")
    return final_result


def _extract_timeline(entities: list) -> list:
    timeline = []
    for entity in entities:
        start = entity.get("start", 0)
        if start and start > 0:
            timeline.append({"timestamp": start, "text": entity.get("text", "")})
    return sorted(timeline, key=lambda x: x["timestamp"])


def main():
    parser = argparse.ArgumentParser(description="Video content analysis and knowledge graph construction - Full Pipeline")
    parser.add_argument("--url", help="Single video URL")
    parser.add_argument("--batch", help="Batch processing (file containing URL list)")
    parser.add_argument("--graph", choices=["networkx", "neo4j"], default="networkx", help="Graph database type (default: networkx)")
    parser.add_argument("--format", choices=["markdown", "word", "both"], default="markdown", help="Report format (default: markdown)")
    parser.add_argument("--use-llm", action="store_true", help="Use LLM-enhanced entity extraction and summarization")
    args = parser.parse_args()

    if args.url:
        result = analyze(args.url, graph=args.graph, fmt=args.format, use_llm=args.use_llm)
        if "error" in result:
            print(f"\nAnalysis failed: {result['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"\nAnalysis complete!")
        print(f"  Document: {result['document_path']}")
        print(f"  Entities: {result['entity_count']}")
        print(f"  Relations: {result['relation_count']}")
        print(f"  Graph nodes added: {result['graph_nodes_added']}")

    elif args.batch:
        url_file = Path(args.batch)
        if not url_file.exists():
            print(f"File not found: {args.batch}", file=sys.stderr)
            sys.exit(1)
        urls = [line.strip() for line in url_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        results = []
        for i, url in enumerate(urls, 1):
            logger.info("Processing %d/%d: %s", i, len(urls), url)
            try:
                result = analyze(url, graph=args.graph, fmt=args.format, use_llm=args.use_llm)
                results.append(result)
            except Exception as e:
                logger.error("Failed to process %s: %s", url, e)
                results.append({"url": url, "error": str(e)})

        print(f"\nBatch complete! Processed {len(results)} videos")
        for i, result in enumerate(results, 1):
            if "error" in result:
                print(f"  {i}. Failed: {result.get('url', '')} - {result['error']}")
            else:
                print(f"  {i}. Success: {result.get('document_path', '')}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
