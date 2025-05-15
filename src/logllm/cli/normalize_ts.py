# src/logllm/cli/normalize_ts.py
import argparse
import multiprocessing
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from ..config import config as cfg
    from ..processors.timestamp_normalizer import TimestampNormalizerAgent
    from ..utils.database import ElasticsearchDatabase
    from ..utils.logger import Logger
except ImportError as e:
    print(f"Error importing modules for 'normalize-ts' CLI: {e}", file=sys.stderr)
    sys.exit(1)

logger = Logger()


# --- Worker for parallel group processing (for 'run' action) ---
def _normalize_group_worker(
    group_name: str, limit: int, batch_size: int
) -> tuple[str, int, int]:
    # ... (implementation remains the same as previously provided) ...
    worker_logger = Logger()
    worker_logger.info(
        f"[Worker-{group_name}] Starting normalization for group '{group_name}'"
    )
    # print(f"[Worker] Starting normalization for group: {group_name}") # Already printed by main thread better

    try:
        db_worker = ElasticsearchDatabase()
        if db_worker.instance is None:
            worker_logger.error(f"[Worker-{group_name}] ES connection failed.")
            print(f"[Worker-{group_name}] Error: Could not connect to Elasticsearch.")
            return group_name, 0, 0

        normalizer_worker = TimestampNormalizerAgent(db_worker)
        processed, indexed = normalizer_worker.process_group(
            group_name, limit=limit, batch_size=batch_size
        )
        worker_logger.info(
            f"[Worker-{group_name}] Finished. Processed: {processed}, Indexed: {indexed}"
        )
        return group_name, processed, indexed
    except Exception as e:
        worker_logger.error(
            f"[Worker-{group_name}] Critical error during normalization: {e}",
            exc_info=True,
        )
        print(f"[Worker-{group_name}] Error processing group: {e}")
        return group_name, 0, 0


# --- Handler for 'run' subcommand (previously handle_normalize_ts) ---
def handle_normalize_ts_run(args):
    logger.info(
        f"Executing normalize-ts run: group='{args.group}', all_groups={args.all_groups}, limit={args.limit}, batch_size={args.batch_size}, threads={args.threads}"
    )
    print("Starting timestamp normalization 'run' process...")
    # ... (rest of the 'run' logic remains the same as previously provided) ...
    try:
        db_main_thread = ElasticsearchDatabase()
        if db_main_thread.instance is None and args.all_groups:
            logger.error(
                "Elasticsearch connection failed (main thread for group listing). Cannot proceed."
            )
            print(
                "Error: Could not connect to Elasticsearch to list groups.",
                file=sys.stderr,
            )
            return

        groups_to_process = []
        if args.all_groups:
            logger.info(
                f"Fetching all group names from '{cfg.INDEX_GROUP_INFOS}' for normalization."
            )
            try:
                query = {"query": {"match_all": {}}}
                group_docs = db_main_thread.scroll_search(
                    query=query, index=cfg.INDEX_GROUP_INFOS
                )
                if group_docs:
                    groups_to_process = list(
                        set(
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
            print(
                "Error: Must specify a group with --group or use --all-groups for 'run'.",
                file=sys.stderr,
            )
            return

        total_processed_all_groups = 0
        total_indexed_all_groups = 0
        group_results_summary = {}

        if args.all_groups and args.threads > 1 and len(groups_to_process) > 1:
            print(
                f"\nProcessing {len(groups_to_process)} groups in parallel using {args.threads} threads..."
            )
            with ThreadPoolExecutor(max_workers=args.threads) as executor:
                future_to_group = {
                    executor.submit(
                        _normalize_group_worker, group_name, args.limit, args.batch_size
                    ): group_name
                    for group_name in groups_to_process
                }
                for future in as_completed(future_to_group):
                    group_name = future_to_group[future]
                    try:
                        _, processed, indexed = future.result()
                        total_processed_all_groups += processed
                        total_indexed_all_groups += indexed
                        group_results_summary[group_name] = {
                            "processed": processed,
                            "indexed": indexed,
                        }
                        print(
                            f"Group '{group_name}' (parallel worker): Processed {processed}, Indexed {indexed}"
                        )
                    except Exception as exc:
                        logger.error(
                            f"Group '{group_name}' generated an exception in parallel worker: {exc}",
                            exc_info=True,
                        )
                        print(
                            f"Error processing group '{group_name}' in worker: {exc}",
                            file=sys.stderr,
                        )
                        group_results_summary[group_name] = {
                            "processed": 0,
                            "indexed": 0,
                            "error": str(exc),
                        }
        else:
            if args.all_groups and len(groups_to_process) > 1:
                print(f"\nProcessing {len(groups_to_process)} groups sequentially...")

            db_sequential = ElasticsearchDatabase()
            if db_sequential.instance is None:
                logger.error(
                    "Elasticsearch connection failed for sequential processing."
                )
                print(
                    "Error: Could not connect to Elasticsearch for sequential processing.",
                    file=sys.stderr,
                )
                return
            normalizer_sequential = TimestampNormalizerAgent(db_sequential)

            for group_name in groups_to_process:
                print(f"\nProcessing group (sequentially): {group_name}")
                try:
                    processed, indexed = normalizer_sequential.process_group(
                        group_name, limit=args.limit, batch_size=args.batch_size
                    )
                    total_processed_all_groups += processed
                    total_indexed_all_groups += indexed
                    group_results_summary[group_name] = {
                        "processed": processed,
                        "indexed": indexed,
                    }
                except Exception as e:
                    logger.error(
                        f"Error processing group '{group_name}' sequentially: {e}",
                        exc_info=True,
                    )
                    print(
                        f"Error processing group '{group_name}' sequentially: {e}",
                        file=sys.stderr,
                    )
                    group_results_summary[group_name] = {
                        "processed": 0,
                        "indexed": 0,
                        "error": str(e),
                    }

        print("\n--- Timestamp Normalization 'Run' Summary ---")
        for g_name, res in group_results_summary.items():
            if "error" in res:
                print(f"  Group '{g_name}': Error - {res['error']}")
            else:
                print(
                    f"  Group '{g_name}': Processed {res['processed']}, Indexed {res['indexed']}"
                )

        print("-" * 20)
        print(f"Total groups considered: {len(groups_to_process)}")
        print(
            f"Total documents processed across all groups (respecting limits): {total_processed_all_groups}"
        )
        print(
            f"Total documents successfully indexed to new 'normalized_*' indices: {total_indexed_all_groups}"
        )
        print("Timestamp normalization 'run' process finished.")

    except Exception as e:
        logger.error(
            f"A critical error occurred during normalize-ts run: {e}", exc_info=True
        )
        print(f"\nAn critical error occurred during 'run': {e}", file=sys.stderr)


# --- NEW Handler for 'delete' subcommand ---
def handle_normalize_ts_delete(args):
    logger.info(
        f"Executing normalize-ts delete: group='{args.group}', all_groups={args.all_groups}"
    )
    print("Starting timestamp normalization 'delete' process...")

    if not args.yes:
        confirm = input(
            "Are you sure you want to delete normalized indices? This action cannot be undone. (yes/no): "
        )
        if confirm.lower() != "yes":
            print("Deletion cancelled by user.")
            return

    try:
        db = ElasticsearchDatabase()
        if db.instance is None:
            logger.error("Elasticsearch connection failed. Cannot proceed with delete.")
            print("Error: Could not connect to Elasticsearch.", file=sys.stderr)
            return

        groups_to_delete_indices_for = []
        if args.all_groups:
            logger.info(
                f"Fetching all group names from '{cfg.INDEX_GROUP_INFOS}' for index deletion."
            )
            try:
                query = {"query": {"match_all": {}}}
                group_docs = db.scroll_search(query=query, index=cfg.INDEX_GROUP_INFOS)
                if group_docs:
                    groups_to_delete_indices_for = list(
                        set(
                            doc["_source"]["group"]
                            for doc in group_docs
                            if doc.get("_source", {}).get("group")
                        )
                    )
                if not groups_to_delete_indices_for:
                    print(
                        f"No groups found in '{cfg.INDEX_GROUP_INFOS}'. No indices to delete based on group names."
                    )
                    return
                logger.info(
                    f"Found {len(groups_to_delete_indices_for)} groups for potential index deletion: {groups_to_delete_indices_for}"
                )
                print(
                    f"Found {len(groups_to_delete_indices_for)} groups. Will attempt to delete corresponding 'normalized_parsed_log_*' indices."
                )
            except Exception as e:
                logger.error(
                    f"Failed to fetch groups from '{cfg.INDEX_GROUP_INFOS}': {e}",
                    exc_info=True,
                )
                print(f"Error fetching groups: {e}", file=sys.stderr)
                return
        elif args.group:
            groups_to_delete_indices_for.append(args.group)
        else:
            print(
                "Error: Must specify a group with --group or use --all-groups for 'delete'.",
                file=sys.stderr,
            )
            return

        deleted_indices_count = 0
        failed_to_delete_indices = []

        for group_name in groups_to_delete_indices_for:
            target_index_to_delete = cfg.get_normalized_parsed_log_storage_index(
                group_name
            )
            print(
                f"\nAttempting to delete index: {target_index_to_delete} (for group: {group_name})"
            )
            try:
                if db.instance.indices.exists(index=target_index_to_delete):
                    db.instance.indices.delete(
                        index=target_index_to_delete, ignore_unavailable=True
                    )
                    logger.info(
                        f"Successfully deleted index '{target_index_to_delete}'."
                    )
                    print(f"  SUCCESS: Deleted index '{target_index_to_delete}'.")
                    deleted_indices_count += 1
                else:
                    logger.info(
                        f"Index '{target_index_to_delete}' does not exist. Nothing to delete."
                    )
                    print(f"  INFO: Index '{target_index_to_delete}' does not exist.")
            except Exception as e:
                logger.error(
                    f"Failed to delete index '{target_index_to_delete}': {e}",
                    exc_info=True,
                )
                print(
                    f"  ERROR: Failed to delete index '{target_index_to_delete}': {e}",
                    file=sys.stderr,
                )
                failed_to_delete_indices.append(target_index_to_delete)

        print("\n--- Timestamp Normalization 'Delete' Summary ---")
        print(
            f"Total groups considered for index deletion: {len(groups_to_delete_indices_for)}"
        )
        print(f"Indices successfully deleted: {deleted_indices_count}")
        if failed_to_delete_indices:
            print(f"Failed to delete indices: {len(failed_to_delete_indices)}")
            for idx_name in failed_to_delete_indices:
                print(f"  - {idx_name}")
        print("Timestamp normalization 'delete' process finished.")

    except Exception as e:
        logger.error(
            f"A critical error occurred during normalize-ts delete: {e}", exc_info=True
        )
        print(f"\nAn critical error occurred during 'delete': {e}", file=sys.stderr)


def register_normalize_ts_parser(subparsers):
    normalize_parser_main = subparsers.add_parser(
        "normalize-ts",
        help="Normalize timestamps in parsed ES logs or delete normalized indices.",
        description="Provides subcommands to 'run' timestamp normalization or 'delete' the resulting normalized indices.",
    )
    # Add subparsers for 'run' and 'delete' actions
    ts_subparsers = normalize_parser_main.add_subparsers(
        dest="normalize_ts_action",
        help="Action to perform (run normalization or delete indices)",
        required=True,
    )

    # --- 'run' Subcommand for normalize-ts ---
    run_parser = ts_subparsers.add_parser(
        "run",
        help="Run the timestamp normalization process on 'parsed_log_*' indices.",
        description="Scans 'parsed_log_*' indices, normalizes timestamps, and stores results in 'normalized_parsed_log_*' indices.",
    )
    run_group_selection_args = run_parser.add_mutually_exclusive_group(required=True)
    run_group_selection_args.add_argument(
        "-g",
        "--group",
        type=str,
        help="Specify a single group name to process (e.g., 'apache').",
    )
    run_group_selection_args.add_argument(
        "-a",
        "--all-groups",
        action="store_true",
        help="Process all groups found in the Elasticsearch group_infos index.",
    )
    run_parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=None,
        help="(Optional) For testing: Limit the number of documents processed per group.",
    )
    run_parser.add_argument(
        "-b",
        "--batch-size",
        type=int,
        default=1000,
        help="Number of documents to process and index in each bulk ES request (default: 1000).",
    )
    default_threads = 1
    try:
        max_threads = multiprocessing.cpu_count()
        max_help_threads = f"Max recommended: {max_threads}."
    except NotImplementedError:
        max_help_threads = "Cannot determine max CPUs."
    run_parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=default_threads,
        help=f"Number of parallel threads if --all-groups is used (default: {default_threads}). {max_help_threads} Ignored if -g is used.",
    )
    run_parser.set_defaults(func=handle_normalize_ts_run)  # Link to 'run' handler

    # --- 'delete' Subcommand for normalize-ts ---
    delete_parser = ts_subparsers.add_parser(
        "delete",
        help="Delete 'normalized_parsed_log_*' indices.",
        description="Deletes the Elasticsearch indices created by the 'normalize-ts run' command.",
    )
    delete_group_selection_args = delete_parser.add_mutually_exclusive_group(
        required=True
    )
    delete_group_selection_args.add_argument(
        "-g",
        "--group",
        type=str,
        help="Specify a single group name whose 'normalized_parsed_log_*' index should be deleted.",
    )
    delete_group_selection_args.add_argument(
        "-a",
        "--all-groups",
        action="store_true",
        help="Delete 'normalized_parsed_log_*' indices for all groups found in the Elasticsearch group_infos index.",
    )
    delete_parser.add_argument(
        "-y", "--yes", action="store_true", help="Confirm deletion without prompting."
    )
    delete_parser.set_defaults(
        func=handle_normalize_ts_delete
    )  # Link to 'delete' handler
