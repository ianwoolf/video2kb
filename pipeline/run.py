#!/usr/bin/env python3
"""
Pipeline 入口 — 视频采集分析服务

加载 .env 环境变量，运行采集分析流水线或补传待发送数据。

Usage:
    python run.py --url "https://youtube.com/watch?v=xxx"
    python run.py --batch urls.txt
    python run.py --retry-pending
    python run.py --url "..." --send false  # 仅分析，不发送
    python run.py --url "..." --no-local-report  # 不生成本地报告

从项目根目录运行:
    cd /data/code/video2kb && python -m pipeline.run --url "xxx"

从 pipeline 目录运行:
    cd /data/code/video2kb/pipeline && python run.py --url "xxx"
"""
import argparse
import logging
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda *a, **kw: None

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

# 项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def load_env():
    """加载 .env 环境变量"""
    # 尝试多个位置
    env_candidates = [
        _PROJECT_ROOT / ".env",
        Path(__file__).resolve().parent / ".env",
    ]
    for env_file in env_candidates:
        if env_file.exists():
            load_dotenv(env_file)
            logger.info("已加载环境变量: %s", env_file)
            break

    # 创建数据目录
    data_base = Path(__file__).resolve().parent / "data"
    for subdir in ["raw", "transcripts", "docs", "pending", "logs"]:
        (data_base / subdir).mkdir(parents=True, exist_ok=True)


def run_single(args):
    """处理单个视频"""
    from pipeline.scripts.run_pipeline import analyze

    result = analyze(
        args.url,
        send=args.send,
        local_report=args.local_report,
        fmt=args.format,
        use_llm=args.use_llm,
        output_base=str(Path(__file__).resolve().parent / "data"),
    )

    if "error" in result:
        logger.error("分析失败: %s", result["error"])
        return 1

    logger.info("分析完成！")
    logger.info("  报告: %s", result.get("document_path", "(无)"))
    logger.info("  实体: %d, 关系: %d", result["entity_count"], result["relation_count"])
    logger.info("  发送状态: %s", result.get("send_status", "skipped"))
    return 0


def run_batch(args):
    """批量处理视频"""
    from pipeline.scripts.run_pipeline import analyze

    url_file = Path(args.batch)
    if not url_file.exists():
        logger.error("文件不存在: %s", args.batch)
        return 1

    urls = [line.strip() for line in url_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    logger.info("批量处理 %d 个视频", len(urls))

    success = 0
    failed = 0
    for i, url in enumerate(urls, 1):
        logger.info("── %d/%d: %s ──", i, len(urls), url)
        try:
            result = analyze(
                url,
                send=args.send,
                local_report=args.local_report,
                fmt=args.format,
                use_llm=args.use_llm,
                output_base=str(Path(__file__).resolve().parent / "data"),
            )
            if "error" in result:
                failed += 1
                logger.error("失败: %s — %s", url, result["error"])
            else:
                success += 1
        except Exception as e:
            failed += 1
            logger.error("异常: %s — %s", url, e)

    logger.info("批量完成: 成功 %d, 失败 %d", success, failed)
    return 0 if failed == 0 else 1


def run_retry_pending(args):
    """补传待发送数据"""
    from pipeline.scripts.data_client import retry_pending

    pending_dir = Path(__file__).resolve().parent / "data" / "pending"
    result = retry_pending(pending_dir=pending_dir)
    logger.info("补传结果: 总计 %d, 成功 %d, 失败 %d, 剩余 %d",
                result["total"], result["sent"], result["failed"], result["remaining"])
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="视频采集分析服务 — Pipeline 入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py --url "https://www.youtube.com/watch?v=xxx"
  python run.py --batch urls.txt
  python run.py --retry-pending
  python run.py --url "..." --no-send
  python run.py --url "..." --format word

流程自动检测是否需要下载音频:
  - YouTube 有字幕 → 不下载音频（更快）
  - YouTube 无字幕 → 下载音频 + ASR
  - Bilibili → 下载音频 + ASR（无字幕提取）

环境变量从 .env 文件加载，参见 .env.example。
        """,
    )

    # 分析选项
    parser.add_argument("--url", help="单个视频 URL")
    parser.add_argument("--batch", help="批量处理（URL 列表文件）")
    parser.add_argument("--retry-pending", action="store_true", help="补传 data/pending/ 中的待发送数据")

    # 控制选项
    parser.add_argument("--send", type=lambda v: v.lower() in ("true", "1", "yes"), default=True,
                        help="是否发送到 KB (默认: true)")
    parser.add_argument("--format", choices=["markdown", "word", "both"], default="markdown",
                        help="报告格式 (默认: markdown)")
    parser.add_argument("--local-report", type=lambda v: v.lower() in ("true", "1", "yes"), default=True,
                        help="是否生成本地报告 (默认: true)")
    parser.add_argument("--use-llm", action="store_true", default=True,
                        help="使用 LLM 增强提取 (默认: true)")
    parser.add_argument("--no-llm", dest="use_llm", action="store_false",
                        help="不使用 LLM 增强提取")

    args = parser.parse_args()

    # 加载环境变量
    load_env()

    # 执行命令
    if args.retry_pending:
        return run_retry_pending(args)
    elif args.url:
        return run_single(args)
    elif args.batch:
        return run_batch(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
