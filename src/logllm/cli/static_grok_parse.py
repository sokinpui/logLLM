# src/logllm/cli/static_grok_parse.py
import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

# Adjust imports to ensure modules from src.logllm are found
try:
    from ..agents.static_grok_parser import StaticGrokParserAgent
    from ..agents.static_grok_parser.api.es_data_service import (
        ElasticsearchDataService,  # For list/delete
    )
    from ..config import config as cfg  # For delete
    from ..utils.database import ElasticsearchDatabase
    from ..utils.logger import Logger
except ImportError:
    # This is a fallback for when the script might be run in a way that Python can't find the modules.
    # For robust CLI, ensure your package is installed or PYTHONPATH is set.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_logllm_dir = os.path.abspath(
        os.path.join(current_dir, "..", "..")
    )  # up to src/logllm
    project_root_dir = os.path.abspath(
        os.path.join(src_logllm_dir, "..")
    )  # up to project root
    if project_root_dir not in sys.path:
        sys.path.insert(0, project_root_dir)
    if (
        src_logllm_dir not in sys.path
    ):  # Also add src/logllm if agents/utils are directly under it
        sys.path.insert(0, src_logllm_dir)

    from src.logllm.agents.static_grok_parser import (
        StaticGrokParserAgent,  # type: ignore
    )
    from src.logllm.agents.static_grok_parser.api.es_data_service import (
        ElasticsearchDataService,  # type: ignore
    )
    from src.logllm.config import config as cfg  # type: ignore
    from src.logllm.utils.database import ElasticsearchDatabase  # type: ignore
    from src.logllm.utils.logger import Logger  # type: ignore


logger = Logger()

DEFAULT_GROK_PATTERNS_FILE = "grok_patterns.yaml"


def handle_static_grok_run(args):
    logger.info(
        f"Executing static-grok-parse run: group='{args.group}', all_groups={args.all_groups}, clear={args.clear}, patterns_file='{args.patterns_file}'"
    )
    print(f"Starting static Grok parsing process...")
    if args.clear:
        print(
            f"WARNING: --clear flag is set. Previously parsed data for selected group(s) will be deleted before parsing."
        )

    db = ElasticsearchDatabase()
    if db.instance is None:
        logger.error("Static Grok Parse CLI: Elasticsearch connection failed.")
        print("Error: Could not connect to Elasticsearch. Aborting.")
        return

    patterns_file = args.patterns_file or DEFAULT_GROK_PATTERNS_FILE
    if not os.path.exists(patterns_file):
        logger.error(f"Grok patterns file not found: {patterns_file}")
        print(
            f"Error: Grok patterns file '{patterns_file}' not found. Please specify a valid path with --grok-patterns-file or ensure '{DEFAULT_GROK_PATTERNS_FILE}' exists."
        )
        return

    agent = StaticGrokParserAgent(db=db, grok_patterns_yaml_path=patterns_file)

    groups_to_clear_param: Optional[List[str]] = None
    clear_all_param: bool = False

    if args.clear:
        if args.all_groups:
            clear_all_param = True
        elif args.group:
            groups_to_clear_param = [args.group]
        else:  # Should be caught by argparser
            print(
                "Error: --clear requires either --group or --all-groups to be specified."
            )
            return

    try:
        # The agent's run method now handles the clearing internally if parameters are passed
        final_state = agent.run(
            clear_records_for_groups=groups_to_clear_param,
            clear_all_group_records=clear_all_param,
        )

        print("\n--- Static Grok Parsing Run Summary (CLI) ---")
        print(f"Overall Orchestrator Status: {final_state.get('orchestrator_status')}")
        if final_state.get("orchestrator_error_messages"):
            print("Orchestrator Errors:")
            for err in final_state.get("orchestrator_error_messages", []):
                print(f"  - {err}")

        for group_name, summary in final_state.get("overall_group_results", {}).items():
            print(
                f"  Group '{group_name}': Status={summary.get('group_status')}, Files Processed Info Count={len(summary.get('files_processed_summary_this_run', {}))}"
            )
            if summary.get("group_error_messages"):
                print(f"    Errors: {summary.get('group_error_messages')}")
        print("Static Grok parsing process finished.")

    except Exception as e:
        logger.error(
            f"Critical error during static Grok parsing run: {e}", exc_info=True
        )
        print(f"An unexpected error occurred: {e}")


def handle_static_grok_list(args):
    logger.info(
        f"Executing static-grok-parse list: group='{args.group}', show_json={args.json}"
    )
    print("Fetching static Grok parsing status...")

    db = ElasticsearchDatabase()
    if db.instance is None:
        logger.error("Static Grok Parse CLI (list): Elasticsearch connection failed.")
        print("Error: Could not connect to Elasticsearch.")
        return

    es_service = ElasticsearchDataService(db)
    status_entries = es_service.get_all_status_entries(group_name=args.group)

    if not status_entries:
        if args.group:
            print(f"No parsing status found for group '{args.group}'.")
        else:
            print("No parsing status entries found in the system.")
        return

    if args.json:
        print(json.dumps(status_entries, indent=2))
    else:
        print(f"\n--- Static Grok Parsing Status ({len(status_entries)} entries) ---")
        for entry in status_entries:
            print(f"  Group: {entry.get('group_name', 'N/A')}")
            print(f"    File ID: {entry.get('log_file_id', 'N/A')}")
            print(f"    Relative Path: {entry.get('log_file_relative_path', 'N/A')}")
            print(
                f"    Last Grok Parsed Line: {entry.get('last_line_parsed_by_grok', 0)}"
            )
            print(
                f"    Collector Total Lines: {entry.get('last_total_lines_by_collector', 0)}"
            )
            print(
                f"    Last Parse Timestamp: {entry.get('last_parse_timestamp', 'N/A')}"
            )
            print(f"    Last Parse Status: {entry.get('last_parse_status', 'N/A')}")
            print("-" * 20)
        print("--- End of Status List ---")


def _confirm_delete_action(group_to_delete: str):
    confirm = input(
        f"Are you sure you want to delete all parsed data and status for '{group_to_delete}'? This cannot be undone. (yes/no): "
    )
    return confirm.lower() == "yes"


def handle_static_grok_delete(args):
    logger.info(
        f"Executing static-grok-parse delete: group='{args.group}', all_groups={args.all_groups}"
    )

    db = ElasticsearchDatabase()
    if db.instance is None:
        logger.error("Static Grok Parse CLI (delete): Elasticsearch connection failed.")
        print("Error: Could not connect to Elasticsearch.")
        return

    es_service = ElasticsearchDataService(db)
    agent_for_clearing = StaticGrokParserAgent(
        db=db, grok_patterns_yaml_path=args.patterns_file or DEFAULT_GROK_PATTERNS_FILE
    )

    groups_to_delete_names: List[str] = []
    if args.all_groups:
        if not args.yes and not _confirm_delete_action("ALL groups"):
            print("Deletion cancelled by user.")
            return
        groups_to_delete_names = es_service.get_all_log_group_names()
        if not groups_to_delete_names:
            print("No groups found in the system to delete.")
            return
        print(
            f"Preparing to delete data for ALL {len(groups_to_delete_names)} groups: {groups_to_delete_names}"
        )
    elif args.group:
        if not args.yes and not _confirm_delete_action(f"group '{args.group}'"):
            print("Deletion cancelled by user.")
            return
        groups_to_delete_names = [args.group]
        print(f"Preparing to delete data for group: {args.group}")
    else:  # Should be caught by argparse
        print("Error: Must specify --group or --all-groups for deletion.")
        return

    total_success = True
    for group_name in groups_to_delete_names:
        print(f"--- Deleting data for group: {group_name} ---")
        try:
            agent_for_clearing._clear_group_data(
                group_name
            )  # Use the agent's internal clear method
            print(f"Successfully cleared data for group: {group_name}")
        except Exception as e:
            logger.error(
                f"Error clearing data for group '{group_name}': {e}", exc_info=True
            )
            print(f"Error clearing data for group '{group_name}': {e}")
            total_success = False

    if total_success and groups_to_delete_names:
        print("\nAll selected group data and statuses have been cleared.")
    elif not groups_to_delete_names:
        pass  # Message already printed if no groups
    else:
        print("\nSome errors occurred during deletion. Please check logs.")


def register_static_grok_parse_parser(subparsers):
    parser = subparsers.add_parser(
        "static-grok-parse",
        help="Parse logs in ES using predefined Grok patterns from a YAML file.",
        description="Processes raw logs stored in Elasticsearch using Grok patterns defined in a YAML file, stores parsed results, and manages parsing status.",
    )
    parser.add_argument(
        "--grok-patterns-file",
        type=str,
        default=None,  # Will use DEFAULT_GROK_PATTERNS_FILE if None
        help=f"Path to the YAML file containing Grok patterns for different groups (default: {DEFAULT_GROK_PATTERNS_FILE} in current dir).",
    )

    action_subparsers = parser.add_subparsers(
        dest="static_grok_action", help="Action to perform", required=True
    )

    # --- 'run' Subcommand ---
    run_parser = action_subparsers.add_parser(
        "run", help="Run the static Grok parsing process."
    )
    run_group = run_parser.add_mutually_exclusive_group(required=True)
    run_group.add_argument(
        "-g", "--group", type=str, help="Specify a single group name to parse."
    )
    run_group.add_argument(
        "-a", "--all-groups", action="store_true", help="Parse all known groups."
    )
    run_parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear previously parsed data and status for the selected group(s) before running.",
    )
    run_parser.set_defaults(func=handle_static_grok_run)

    # --- 'list' Subcommand ---
    list_parser = action_subparsers.add_parser(
        "list", help="List the Grok parsing status for files/groups."
    )
    list_parser.add_argument(
        "-g", "--group", type=str, help="Filter status list by a specific group name."
    )
    list_parser.add_argument(
        "--json", action="store_true", help="Output the status list in JSON format."
    )
    list_parser.set_defaults(func=handle_static_grok_list)

    # --- 'delete' Subcommand ---
    delete_parser = action_subparsers.add_parser(
        "delete", help="Delete parsed data and status for groups."
    )
    delete_group = delete_parser.add_mutually_exclusive_group(required=True)
    delete_group.add_argument(
        "-g",
        "--group",
        type=str,
        help="Specify a single group whose parsed data and status should be deleted.",
    )
    delete_group.add_argument(
        "-a",
        "--all-groups",
        action="store_true",
        help="Delete parsed data and status for ALL groups.",
    )
    delete_parser.add_argument(
        "-y", "--yes", action="store_true", help="Confirm deletion without prompting."
    )
    delete_parser.set_defaults(func=handle_static_grok_delete)
