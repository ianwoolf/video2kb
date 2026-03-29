#!/usr/bin/env python3
"""
Video Analysis Pipeline Runner

Loads environment variables from .env file and runs the pipeline scripts.

Usage:
    python run.py --url "https://youtube.com/watch?v=xxx"
    python run.py --batch urls.txt
    python run.py --query "entity_name"
"""
import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print("Warning: python-dotenv not installed. Install with: pip install python-dotenv")
    print("Environment variables will be loaded from system only.")
    load_dotenv = lambda *args, **kwargs: None


def load_env():
    """Load environment variables from .env file"""
    project_root = Path(__file__).parent
    env_file = project_root / ".env"

    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded environment from: {env_file}")
    else:
        print(f"Warning: .env file not found at {env_file}")
        print("Using default environment variables.")

    # Create data directories
    data_dir = project_root / "data"
    for subdir in ["raw", "transcripts", "docs"]:
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)


def run_pipeline(args):
    """Run the pipeline script with given arguments"""
    import subprocess

    script_dir = Path(__file__).parent / "scripts"
    pipeline_script = script_dir / "run_pipeline.py"

    cmd = [sys.executable, str(pipeline_script)]
    if args.url:
        cmd.extend(["--url", args.url])
    if args.batch:
        cmd.extend(["--batch", args.batch])
    if args.graph:
        cmd.extend(["--graph", args.graph])
    if args.format:
        cmd.extend(["--format", args.format])
    if args.use_llm:
        cmd.append("--use-llm")

    return subprocess.run(cmd)


def run_query(entity_name):
    """Query the knowledge graph"""
    import subprocess

    script_dir = Path(__file__).parent / "scripts"
    query_script = script_dir / "graph_query.py"

    cmd = [sys.executable, str(query_script), "--entity", entity_name]
    return subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(
        description="Video Analysis Pipeline - Load .env and run analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py --url "https://www.youtube.com/watch?v=xxx"
  python run.py --batch urls.txt
  python run.py --query "entity_name"
  python run.py --url "..." --graph neo4j --format word

The pipeline automatically detects if audio download is needed:
  - YouTube with subtitles → No audio download (faster)
  - YouTube without subtitles → Audio download + ASR
  - Bilibili → Audio download + ASR (no subtitle extraction)

Environment variables are loaded from .env file in the project root.
See .env.example for available options.
        """
    )

    # Analysis options
    parser.add_argument("--url", help="Single video URL")
    parser.add_argument("--batch", help="Batch processing (file containing URL list)")
    parser.add_argument("--query", help="Query knowledge graph for entity")
    parser.add_argument("--graph", choices=["networkx", "neo4j"], help="Graph database type")
    parser.add_argument("--format", choices=["markdown", "word", "both"], help="Report format")
    parser.add_argument("--use-llm", action="store_true", help="Use LLM-enhanced extraction")

    args = parser.parse_args()

    # Load environment variables
    load_env()

    # Execute command
    if args.query:
        return run_query(args.query)
    elif args.url or args.batch:
        return run_pipeline(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
