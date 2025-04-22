# src/logllm/cli/collect.py
import argparse
import os
from ..utils.collector import Collector
from ..utils.database import ElasticsearchDatabase
from ..utils.logger import Logger

logger = Logger()


def handle_collect(args):
    logger.info(f"Executing collect command for directory: {args.directory}")
    if not os.path.isdir(args.directory):
        logger.error(f"Directory not found: {args.directory}")
        print(f"Error: Directory not found: {args.directory}")
        return

    try:
        es_db = ElasticsearchDatabase()
        if es_db.instance is None:
            logger.error("Failed to connect to Elasticsearch. Cannot collect logs.")
            print("Error: Could not connect to Elasticsearch. Ensure it's running.")
            return

        collector = Collector(args.directory)  # Collector initializes file scanning

        if not collector.collected_files:
            logger.warning(f"No log files found in {args.directory}")
            print(f"Warning: No log files found in {args.directory}")
            return

        logger.info(
            f"Found {len(collector.collected_files)} log files. Starting insertion..."
        )
        # Using the efficient method for potentially large logs
        collector.insert_very_large_logs_into_db(
            db=es_db, files=collector.collected_files
        )

        logger.info("Log collection and insertion finished.")
        print("Log collection finished.")

    except Exception as e:
        logger.error(f"An error occurred during collection: {e}")
        print(f"An error occurred during collection: {e}")


def register_collect_parser(subparsers):
    collect_parser = subparsers.add_parser(
        "collect", help="Collect logs from a directory and insert into Elasticsearch"
    )
    collect_parser.add_argument(
        "-d",
        "--directory",
        type=str,
        required=True,
        help="Path to the directory containing log files",
    )
    collect_parser.set_defaults(func=handle_collect)
