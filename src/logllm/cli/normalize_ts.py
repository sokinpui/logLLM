# src/logllm/cli/normalize_ts.py
import argparse
import sys

try:
    from ..config import config as cfg
    from ..processors.timestamp_normalizer import TimestampNormalizerAgent
    from ..utils.database import ElasticsearchDatabase
    from ..utils.logger import Logger
except ImportError as e:
    print(f"Error importing modules for 'normalize-ts' CLI: {e}", file=sys.stderr)
    sys.exit(1)

logger = Logger()


def handle_normalize_ts(args):
    logger.info(
        f"Executing normalize-ts: group='{args.group}', all_groups={args.all_groups}, limit={args.limit}, batch_size={args.batch_size}"
    )
    print("Starting timestamp normalization process...")

    try:
        db = ElasticsearchDatabase()
        if db.instance is None:
            logger.error("Elasticsearch connection failed. Cannot proceed.")
            print("Error: Could not connect to Elasticsearch.", file=sys.stderr)
            return

        normalizer = TimestampNormalizerAgent(db)

        groups_to_process = []
        if args.all_groups:
            logger.info(
                f"Fetching all group names from '{cfg.INDEX_GROUP_INFOS}' for normalization."
            )
            try:
                query = {"query": {"match_all": {}}}
                # Using scroll_search to get all group documents
                group_docs = db.scroll_search(query=query, index=cfg.INDEX_GROUP_INFOS)
                if group_docs:
                    groups_to_process = list(
                        set(  # Use set to ensure uniqueness
                            doc["_source"]["group"]
                            for doc in group_docs
                            if doc.get("_source", {}).get("group")
                        )
                    )
                if not groups_to_process:
                    print("No groups found in group_infos index. Nothing to process.")
                    return
                logger.info(
                    f"Found {len(groups_to_process)} unique groups to process: {groups_to_process}"
                )
                print(f"Found {len(groups_to_process)} groups to process.")
            except Exception as e:
                logger.error(
                    f"Failed to fetch groups from '{cfg.INDEX_GROUP_INFOS}': {e}",
                    exc_info=True,
                )
                print(f"Error fetching groups: {e}", file=sys.stderr)
                return
        elif args.group:
            groups_to_process.append(args.group)
        else:
            # This case should be handled by argparse if the group is made required
            print(
                "Error: Must specify a group with --group or use --all-groups.",
                file=sys.stderr,
            )
            return

        total_processed_all_groups = 0
        total_indexed_all_groups = 0

        for group_name in groups_to_process:
            print(f"\nProcessing group: {group_name}")
            processed, indexed = normalizer.process_group(
                group_name, limit=args.limit, batch_size=args.batch_size
            )
            total_processed_all_groups += processed
            total_indexed_all_groups += indexed

        print("\n--- Timestamp Normalization Summary ---")
        print(f"Total groups considered: {len(groups_to_process)}")
        print(
            f"Total documents processed across all groups (respecting limits): {total_processed_all_groups}"
        )
        print(
            f"Total documents successfully indexed to new 'normalized_*' indices: {total_indexed_all_groups}"
        )
        print("Timestamp normalization process finished.")

    except Exception as e:
        logger.error(
            f"A critical error occurred during normalize-ts execution: {e}",
            exc_info=True,
        )
        print(f"\nAn critical error occurred: {e}", file=sys.stderr)
        # import traceback; traceback.print_exc() # Uncomment for direct debugging


def register_normalize_ts_parser(subparsers):
    normalize_parser = subparsers.add_parser(
        "normalize-ts",
        help="Normalize timestamps in parsed ES logs (from 'parsed_log_*' indices).",
        description="Scans 'parsed_log_*' indices, attempts to parse various timestamp fields, normalizes them to UTC ISO 8601 in '@timestamp', and stores results in new 'normalized_parsed_log_*' indices.",
    )

    group_selection_args = normalize_parser.add_mutually_exclusive_group(required=True)
    group_selection_args.add_argument(
        "-g",
        "--group",
        type=str,
        help="Specify a single group name to process (e.g., 'apache').",
    )
    group_selection_args.add_argument(
        "-a",
        "--all-groups",
        action="store_true",
        help="Process all groups found in the Elasticsearch group_infos index.",
    )

    normalize_parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=None,
        help="(Optional) For testing: Limit the number of documents processed per group.",
    )
    normalize_parser.add_argument(
        "-b",
        "--batch-size",
        type=int,
        default=1000,  # Smaller default for potentially more complex docs
        help="Number of documents to process and index in each bulk ES request (default: 1000).",
    )

    normalize_parser.set_defaults(func=handle_normalize_ts)
