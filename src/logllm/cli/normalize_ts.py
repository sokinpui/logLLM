# src/logllm/cli/normalize_ts.py
import argparse
import sys
from typing import List, Optional

try:
    from ..agents.timestamp_normalizer import (  # Import the new agent and default
        DEFAULT_BATCH_SIZE_NORMALIZER,
        TimestampNormalizerAgent,
    )
    from ..agents.timestamp_normalizer.states import (
        TimestampNormalizerOrchestratorState,
    )
    from ..config import config as cfg
    from ..utils.database import ElasticsearchDatabase
    from ..utils.logger import Logger
except ImportError as e:
    print(f"Error importing modules for 'normalize-ts' CLI: {e}", file=sys.stderr)
    sys.exit(1)

logger = Logger()


def _print_run_summary(
    final_state: TimestampNormalizerOrchestratorState, action_description: str
):
    print(f"\n--- Timestamp Normalization '{action_description}' Summary ---")
    orchestrator_status = final_state.get("orchestrator_status", "unknown")
    print(f"Overall Orchestrator Status: {orchestrator_status}")

    if final_state.get("orchestrator_error_messages"):
        print("Orchestrator Errors:")
        for err in final_state.get("orchestrator_error_messages", []):
            print(f"  - {err}")

    total_scanned_all = 0
    total_updated_all = 0
    total_norm_errors_all = 0

    for group_name, group_data in final_state.get("overall_group_results", {}).items():
        status = group_data.get("status_this_run", "N/A")
        scanned = group_data.get("documents_scanned_this_run", 0)
        updated = group_data.get("documents_updated_this_run", 0)
        norm_errors = group_data.get("timestamp_normalization_errors_this_run", 0)
        error_msg = group_data.get("error_message_this_run")

        total_scanned_all += scanned
        total_updated_all += updated
        if final_state.get("action_to_perform") == "normalize":
            total_norm_errors_all += norm_errors

        print(f"\n  Group '{group_name}':")
        print(f"    Status: {status}")
        if error_msg:
            print(f"    Error: {error_msg}")
        print(f"    Documents Scanned/Considered: {scanned}")
        print(f"    Documents Updated: {updated}")
        if final_state.get("action_to_perform") == "normalize":
            print(f"    Timestamp Normalization Errors: {norm_errors}")

    print("-" * 20)
    print(
        f"Total groups processed: {len(final_state.get('overall_group_results', {}))}"
    )
    print(f"Total documents scanned/considered across all groups: {total_scanned_all}")
    print(f"Total documents updated across all groups: {total_updated_all}")
    if final_state.get("action_to_perform") == "normalize":
        print(
            f"Total timestamp normalization errors across all groups: {total_norm_errors_all}"
        )

    print(f"Timestamp normalization '{action_description}' process finished.")


# --- Handler for 'run' subcommand ---
def handle_normalize_ts_run(args):
    action_description = "Run (Normalize Timestamps)"
    logger.info(
        f"Executing normalize-ts {action_description}: group='{args.group}', all_groups={args.all_groups}, limit={args.limit}, batch_size={args.batch_size}"
    )
    print(f"Starting timestamp normalization '{action_description}' process...")

    try:
        db_main = ElasticsearchDatabase()
        if db_main.instance is None:
            logger.error("Elasticsearch connection failed. Cannot proceed.")
            print("Error: Could not connect to Elasticsearch.", file=sys.stderr)
            return

        agent = TimestampNormalizerAgent(db=db_main)

        target_groups: Optional[List[str]] = None
        if args.group:
            target_groups = [args.group]

        final_state = agent.run(
            action="normalize",
            target_groups=target_groups,
            limit_per_group=args.limit,
            batch_size=args.batch_size,
        )
        _print_run_summary(final_state, action_description)

    except Exception as e:
        logger.error(
            f"A critical error occurred during normalize-ts {action_description}: {e}",
            exc_info=True,
        )
        print(
            f"\nAn critical error occurred during '{action_description}': {e}",
            file=sys.stderr,
        )


# --- Handler for 'delete' subcommand ---
def handle_normalize_ts_delete(args):
    action_description = "Delete (@timestamp field)"
    logger.info(
        f"Executing normalize-ts {action_description}: group='{args.group}', all_groups={args.all_groups}, batch_size={args.batch_size}"
    )
    print(f"Starting process to '{action_description}' from 'parsed_log_*' indices...")

    if not args.yes:
        confirm = input(
            "Are you sure you want to remove the '@timestamp' field from the selected parsed log indices? This action modifies data. (yes/no): "
        )
        if confirm.lower() != "yes":
            print("Field removal cancelled by user.")
            return

    try:
        db_main = ElasticsearchDatabase()
        if db_main.instance is None:
            logger.error("Elasticsearch connection failed. Cannot proceed.")
            print("Error: Could not connect to Elasticsearch.", file=sys.stderr)
            return

        agent = TimestampNormalizerAgent(db=db_main)

        target_groups: Optional[List[str]] = None
        if args.group:
            target_groups = [args.group]

        final_state = agent.run(
            action="remove_field",
            target_groups=target_groups,
            batch_size=args.batch_size,
        )
        _print_run_summary(final_state, action_description)

    except Exception as e:
        logger.error(
            f"A critical error occurred during normalize-ts {action_description}: {e}",
            exc_info=True,
        )
        print(
            f"\nAn critical error occurred during '{action_description}': {e}",
            file=sys.stderr,
        )


def register_normalize_ts_parser(subparsers):
    normalize_parser_main = subparsers.add_parser(
        "normalize-ts",
        help="Normalize timestamps in parsed ES logs (in-place) or delete the '@timestamp' field.",
        description="Provides subcommands to 'run' in-place timestamp normalization on 'parsed_log_*' indices, or 'delete' the '@timestamp' field from them. The agent processes groups sequentially.",
    )
    ts_subparsers = normalize_parser_main.add_subparsers(
        dest="normalize_ts_action",
        help="Action to perform (run normalization or delete '@timestamp' field)",
        required=True,
    )

    # --- 'run' Subcommand for normalize-ts ---
    run_parser = ts_subparsers.add_parser(
        "run",
        help="Run in-place timestamp normalization on 'parsed_log_*' indices.",
        description="Scans 'parsed_log_*' indices, normalizes 'timestamp' field to '@timestamp' (ISO8601 UTC) in-place.",
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
        default=DEFAULT_BATCH_SIZE_NORMALIZER,  # Use the new default
        help=f"Number of documents to process and update in each bulk ES request (default: {DEFAULT_BATCH_SIZE_NORMALIZER}).",
    )
    run_parser.set_defaults(func=handle_normalize_ts_run)

    # --- 'delete' Subcommand for normalize-ts ---
    delete_parser = ts_subparsers.add_parser(
        "delete",
        help="Delete (remove) the '@timestamp' field from 'parsed_log_*' indices.",
        description="Removes the '@timestamp' field from documents in 'parsed_log_*' indices, effectively undoing the 'run' action.",
    )
    delete_group_selection_args = delete_parser.add_mutually_exclusive_group(
        required=True
    )
    delete_group_selection_args.add_argument(
        "-g",
        "--group",
        type=str,
        help="Specify a single group name whose 'parsed_log_*' index should have '@timestamp' removed.",
    )
    delete_group_selection_args.add_argument(
        "-a",
        "--all-groups",
        action="store_true",
        help="Remove '@timestamp' field from 'parsed_log_*' indices for all groups found in group_infos.",
    )
    delete_parser.add_argument(
        "-b",
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE_NORMALIZER,  # Use the new default
        help=f"Number of documents to process in each bulk ES request for field removal (default: {DEFAULT_BATCH_SIZE_NORMALIZER}).",
    )
    delete_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Confirm field removal without prompting.",
    )
    delete_parser.set_defaults(func=handle_normalize_ts_delete)
