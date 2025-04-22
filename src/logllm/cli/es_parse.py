# src/logllm/cli/es_parse.py

import argparse
import sys
import multiprocessing
import os

# Add json import for --json flag
import json

# Add datetime and potentially timezone handling if needed later
from datetime import datetime
from elasticsearch import NotFoundError
from typing import Dict, Any, List, Optional, Tuple  # Add Optional, Tuple

try:
    from ..agents.es_parser_agent import (
        AllGroupsParserAgent,
        SingleGroupParserAgent,
        AllGroupsParserState,
        SingleGroupParseGraphState,
    )
    from ..utils.llm_model import GeminiModel
    from ..utils.database import ElasticsearchDatabase
    from ..utils.logger import Logger
    from ..utils.prompts_manager import PromptsManager
    from ..config import config as cfg
except ImportError as e:
    print(f"Error importing necessary modules for CLI 'es-parse' command: {e}")
    sys.exit(1)

logger = Logger()


# --- Original handle_es_parse (for 'run' subcommand) ---
# (Keep the existing handle_es_parse function as is)
def handle_es_parse(args):
    """Handles the logic for the 'es-parse run' command using the new agents."""
    num_threads = args.threads
    batch_size = args.batch_size
    sample_size = args.sample_size  # Used for generation
    target_group = args.group
    field_to_parse = args.field
    fields_to_copy = args.copy_fields
    provided_pattern = args.pattern  # Get pattern if provided
    keep_unparsed = args.keep_unparsed  # Get the keep flag

    # --- Get new config options from args ---
    validation_sample_size = args.validation_sample_size
    validation_threshold = args.validation_threshold
    max_regeneration_attempts = args.max_retries  # Renamed arg

    # --- Validate Inputs ---
    if num_threads < 1:
        num_threads = 1
    if batch_size < 1:
        batch_size = 1000
    if sample_size < 1:
        sample_size = 10
    if validation_sample_size < 1:
        validation_sample_size = 10
    if not (0.0 <= validation_threshold <= 1.0):
        validation_threshold = 0.5
    if max_regeneration_attempts < 0:
        max_regeneration_attempts = 0  # 0 retries means 1 attempt

    # --- Check pattern requires group ---
    if provided_pattern and not target_group:
        msg = "The --pattern argument requires the --group argument to be specified."
        logger.error(msg)
        print(f"Error: {msg}")
        sys.exit(1)

    # Log execution mode
    if target_group:
        effective_num_threads = 1
        logger.info(
            f"Executing ES parse for SINGLE group: '{target_group}'. Batch: {batch_size}, GenSample: {sample_size}, ValSample: {validation_sample_size}, Retries: {max_regeneration_attempts}"
        )
        print(f"Starting ES log parsing for SINGLE group: '{target_group}'.")
    else:
        effective_num_threads = num_threads
        logger.info(
            f"Executing ES parse for ALL groups. Workers: {effective_num_threads}, Batch: {batch_size}, GenSample: {sample_size}, ValSample: {validation_sample_size}, Retries: {max_regeneration_attempts}"
        )
        print(
            f"Starting ES log parsing for ALL groups. Workers: {effective_num_threads}"
        )

    try:
        # --- Initialize Dependencies (Common) ---
        logger.info("Initializing components for Elasticsearch parsing...")
        db = ElasticsearchDatabase()
        if db.instance is None:
            logger.error("Elasticsearch connection failed. Cannot proceed.")
            print("Error: Could not connect to Elasticsearch.")
            return

        model = GeminiModel()  # Ensure API key is set
        json_file_path = getattr(args, "json", None) or (
            "prompts/test.json"
            if getattr(args, "test", False)
            else "prompts/prompts.json"
        )
        prompts_manager = PromptsManager(json_file=json_file_path)

        # --- Branch Logic: Single Group vs All Groups ---

        if target_group:
            # --- SINGLE GROUP Parsing ---
            logger.info(
                f"Instantiating SingleGroupParserAgent for group '{target_group}'"
            )
            agent = SingleGroupParserAgent(
                model=model, db=db, prompts_manager=prompts_manager
            )

            # Prepare the config dictionary for the agent's run method
            single_group_config: Dict[str, Any] = {
                "group_name": target_group,
                "field_to_parse": field_to_parse,
                "fields_to_copy": fields_to_copy,
                "batch_size": batch_size,
                "sample_size_generation": sample_size,  # Map arg to state key
                "sample_size_validation": validation_sample_size,
                "validation_threshold": validation_threshold,
                "max_regeneration_attempts": max_regeneration_attempts
                + 1,  # Agent expects max *attempts*
                "provided_grok_pattern": provided_pattern,  # Pass the pattern
                "keep_unparsed_index": keep_unparsed,  # Pass the flag
            }

            # Run the agent (which executes its internal graph)
            final_group_state: SingleGroupParseGraphState | Dict[str, Any] = agent.run(
                single_group_config
            )

            # --- Display Summary (Single Group - using new state) ---
            print("\n--- Elasticsearch Parsing Summary (Single Group) ---")
            status = final_group_state.get("final_parsing_status", "unknown")
            # Use the summary dictionary now
            results_summary = final_group_state.get("final_parsing_results_summary")
            error_msgs = final_group_state.get("error_messages", [])

            pattern_used = final_group_state.get("current_grok_pattern", "N/A")
            if status == "success_fallback":
                pattern_used = "Fallback: " + SingleGroupParserAgent.FALLBACK_PATTERN
            elif status == "failed_fallback":
                pattern_used = "Fallback FAILED"
            elif "failed" in status:
                pattern_used = "Failed before/during parsing"
            elif not pattern_used or pattern_used == "N/A":
                pattern_used = "Pattern Generation/Validation Failed"

            # Extract counts from the summary dict
            processed = results_summary.get("processed", 0) if results_summary else 0
            indexed_ok = results_summary.get("successful", 0) if results_summary else 0
            indexed_failed_fallback = (
                results_summary.get("failed", 0) if results_summary else 0
            )  # Docs sent to failed index
            parse_errors = (
                results_summary.get("parse_errors", 0) if results_summary else 0
            )  # Grok mismatches
            index_errors = (
                results_summary.get("index_errors", 0) if results_summary else 0
            )  # Bulk API errors

            target_idx_name = cfg.get_parsed_log_storage_index(target_group)
            failed_idx_name = cfg.get_unparsed_log_storage_index(target_group)

            print(f"\nGroup '{target_group}':")
            print(f"  Status: {status}")
            print(f"  Pattern Detail: {pattern_used}")
            print(f"  Docs Scanned: {processed}")
            print(
                f"  Indexed Successfully (-> {os.path.basename(target_idx_name)}): {indexed_ok}"
            )
            print(
                f"  Failed/Fallback (-> {os.path.basename(failed_idx_name)}): {indexed_failed_fallback}"
            )
            print(f"  Grok Parse Errors (within run): {parse_errors}")
            print(f"  Bulk Indexing Errors: {index_errors}")

            if error_msgs:
                print("  Agent Errors/Warnings:")
                for i, msg in enumerate(error_msgs[:5]):
                    print(f"    - {msg}")
                if len(error_msgs) > 5:
                    print("    ...")

            if status in ["success", "success_with_errors", "success_fallback"]:
                if parse_errors == 0 and index_errors == 0 and not error_msgs:
                    print("\nResult: SUCCESSFUL (details above)")
                else:
                    print("\nResult: COMPLETED WITH ERRORS/FAILURES (details above)")
            else:
                print("\nResult: FAILED")

            logger.info(
                f"Single group ('{target_group}') parsing finished. Final Status: {status}"
            )

        else:
            # --- ALL GROUPS Parsing ---
            logger.info("Instantiating AllGroupsParserAgent")
            agent = AllGroupsParserAgent(
                model=model, db=db, prompts_manager=prompts_manager
            )

            initial_orchestrator_state: AllGroupsParserState = {
                "group_info_index": cfg.INDEX_GROUP_INFOS,
                "field_to_parse": field_to_parse,
                "fields_to_copy": fields_to_copy,
                "group_results": {},
                "status": "pending",
            }

            # Run the orchestrator agent, passing necessary parameters
            final_orchestrator_state = agent.run(
                initial_state=initial_orchestrator_state,
                num_threads=effective_num_threads,
                batch_size=batch_size,
                sample_size=sample_size,
                validation_sample_size=validation_sample_size,
                validation_threshold=validation_threshold,
                max_regeneration_attempts=max_regeneration_attempts + 1,
                keep_unparsed_index=keep_unparsed,  # Pass flag
                # provided_grok_pattern is implicitly None here for all groups run
            )

            # --- Display Summary (All Groups - using new state) ---
            print("\n--- Elasticsearch Parsing Summary (All Groups) ---")
            if final_orchestrator_state["status"] == "completed":
                group_results_dict = final_orchestrator_state.get("group_results", {})
                total_groups = len(group_results_dict)
                success_count = 0
                success_errors_count = 0
                fallback_count = 0
                failed_count = 0

                total_processed_all = 0
                total_indexed_ok_all = 0
                total_indexed_failed_fallback_all = 0
                total_parse_errors_all = 0
                total_index_errors_all = 0

                print(f"Processed {total_groups} groups.")

                for group_name, group_final_state in group_results_dict.items():
                    status = group_final_state.get("final_parsing_status", "unknown")
                    results_summary = group_final_state.get(
                        "final_parsing_results_summary"
                    )
                    error_msgs = group_final_state.get("error_messages", [])

                    pattern_used = group_final_state.get("current_grok_pattern", "N/A")
                    if status == "success_fallback":
                        pattern_used = (
                            "Fallback: " + SingleGroupParserAgent.FALLBACK_PATTERN
                        )
                    elif "failed" in status:
                        pattern_used = f"Failed (see logs)"
                    elif not pattern_used:
                        pattern_used = "N/A (Generation/Validation Failed)"

                    processed = (
                        results_summary.get("processed", 0) if results_summary else 0
                    )
                    indexed_ok = (
                        results_summary.get("successful", 0) if results_summary else 0
                    )
                    indexed_failed_fallback = (
                        results_summary.get("failed", 0) if results_summary else 0
                    )
                    parse_errors = (
                        results_summary.get("parse_errors", 0) if results_summary else 0
                    )
                    index_errors = (
                        results_summary.get("index_errors", 0) if results_summary else 0
                    )

                    target_idx_name = cfg.get_parsed_log_storage_index(group_name)
                    failed_idx_name = cfg.get_unparsed_log_storage_index(group_name)

                    print(f"\nGroup '{group_name}':")
                    print(f"  Status: {status}")
                    print(f"  Pattern Detail: {pattern_used}")
                    print(f"  Docs Scanned: {processed}")
                    print(
                        f"  Indexed Successfully (-> {os.path.basename(target_idx_name)}): {indexed_ok}"
                    )
                    print(
                        f"  Failed/Fallback (-> {os.path.basename(failed_idx_name)}): {indexed_failed_fallback}"
                    )
                    print(
                        f"  Grok Parse Errors: {parse_errors}, Bulk Index Errors: {index_errors}"
                    )
                    if error_msgs:
                        print(f"  Agent Errors/Warnings: {len(error_msgs)} (See logs)")

                    # Update overall counters
                    if status == "success":
                        success_count += 1
                    elif status == "success_with_errors":
                        success_errors_count += 1
                    elif status == "success_fallback":
                        fallback_count += 1
                    else:
                        failed_count += 1

                    total_processed_all += processed
                    total_indexed_ok_all += indexed_ok
                    total_indexed_failed_fallback_all += indexed_failed_fallback
                    total_parse_errors_all += parse_errors
                    total_index_errors_all += index_errors

                print("\n--- Overall ---")
                print(f"Total Groups Processed: {total_groups}")
                print(f"  Success (Clean): {success_count}")
                print(f"  Success (with Errors/Parse Failures): {success_errors_count}")
                print(f"  Success (Fallback Pattern): {fallback_count}")
                print(f"  Failed: {failed_count}")
                print("-" * 20)
                print(f"Total Documents Scanned: {total_processed_all}")
                print(
                    f"Total Successfully Indexed (Target Indices): {total_indexed_ok_all}"
                )
                print(
                    f"Total Failed/Fallback Indexed (Failed Indices): {total_indexed_failed_fallback_all}"
                )
                print(f"Total Grok Parse Errors: {total_parse_errors_all}")
                print(f"Total Bulk Indexing Errors: {total_index_errors_all}")

            else:
                print(
                    f"Overall Status: FAILED ({final_orchestrator_state.get('status', 'unknown')})"
                )
                print("Check logs for detailed errors during orchestration.")

            logger.info("All groups parsing finished.")

    except Exception as e:
        logger.error(
            f"An critical error occurred during es-parse execution: {e}", exc_info=True
        )
        print(f"\nAn critical error occurred: {e}")
        import traceback

        traceback.print_exc()


# --- Updated _print_result_entry ---
def _print_result_entry(doc_source: dict):
    """Formats and prints a single entry from the grok_results_history index."""
    group = doc_source.get("group_name", "N/A")
    status = doc_source.get("parsing_status", "unknown")
    pattern = doc_source.get("grok_pattern_used", "N/A")
    timestamp_iso = doc_source.get("timestamp")
    processed = doc_source.get("processed_count", 0)
    successful = doc_source.get("successful_count", 0)
    failed = doc_source.get("failed_count", 0)
    parse_errors = doc_source.get("parse_error_count", 0)
    index_errors = doc_source.get("index_error_count", 0)
    agent_errors = doc_source.get("agent_error_count", 0)

    # --- Consistent Timestamp Formatting ---
    # Define the format used for display
    DISPLAY_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
    try:
        if timestamp_iso:
            # Parse ISO format (handle potential Z or timezone offsets if needed)
            dt_obj = datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
            # Format to the consistent display format
            timestamp_str = dt_obj.strftime(DISPLAY_TIMESTAMP_FORMAT)
        else:
            timestamp_str = "N/A"
    except ValueError:
        timestamp_str = f"Invalid ({timestamp_iso})"
    # --------------------------------------

    target_idx_name = cfg.get_parsed_log_storage_index(group)
    unparsed_idx_name = cfg.get_unparsed_log_storage_index(group)

    print(f"\nGroup '{group}' (Recorded: {timestamp_str}):")  # Use formatted time
    print(f"  Status: {status}")
    print(f"  Pattern Detail: {pattern}")
    print(f"  Docs Scanned: {processed}")
    print(
        f"  Indexed Successfully (-> {os.path.basename(target_idx_name)}): {successful}"
    )
    print(f"  Failed/Fallback (-> {os.path.basename(unparsed_idx_name)}): {failed}")
    print(f"  Grok Parse Errors: {parse_errors}, Bulk Index Errors: {index_errors}")
    if agent_errors > 0:
        print(f"  Agent Errors/Warnings: {agent_errors} (See logs for details)")


# --- Updated handle_es_parse_list ---
def handle_es_parse_list(args):
    """Handles the logic for the 'es-parse list' command."""
    logger.info(
        f"Executing es-parse list: group={args.group}, all_history={args.all}, group_name_only={args.group_name}, json_output={args.json}"
    )
    group_filter = args.group
    show_all_history = args.all
    group_name_only = args.group_name
    json_output = args.json
    history_index = cfg.INDEX_GROK_RESULTS_HISTORY  # Use correct config var

    if group_name_only and json_output:
        logger.warning(
            "Both --group-name and --json requested. Outputting group names as JSON list."
        )
        # Proceed with group_name_only logic, but format output as JSON

    try:
        db = ElasticsearchDatabase()
        if db.instance is None:
            logger.error("ES connection failed for listing results.")
            print("Error: Could not connect to Elasticsearch.")
            return

        if not db.instance.indices.exists(index=history_index):
            logger.warning(f"History index '{history_index}' not found.")
            print(
                f"Error: Grok results history index '{history_index}' does not exist. Run 'es-parse run' first."
            )
            return

        # --- Handle --group-name logic first ---
        if group_name_only:
            logger.info("Fetching unique group names...")
            group_field_keyword = (
                "group_name.keyword"  # Use keyword field for aggregation
            )
            try:
                # Use terms aggregation to get unique group names
                response = db.instance.search(
                    index=history_index,
                    size=0,  # Don't need hits, just aggregation
                    aggs={
                        "unique_groups": {
                            "terms": {
                                "field": group_field_keyword,
                                "size": 10000,
                            }  # Adjust size if needed
                        }
                    },
                )
                group_names = [
                    bucket["key"]
                    for bucket in response.get("aggregations", {})
                    .get("unique_groups", {})
                    .get("buckets", [])
                ]
                group_names.sort()  # Sort for consistency

                if json_output:  # If --json was also specified
                    print(json.dumps(group_names, indent=2))
                elif group_names:
                    print("Groups found in history:")
                    for name in group_names:
                        print(f"- {name}")
                else:
                    print("No groups found in history.")
                return  # Exit after printing group names

            except Exception as agg_e:
                logger.error(
                    f"Error fetching unique group names: {agg_e}", exc_info=True
                )
                print(f"Error fetching unique group names: {agg_e}")
                return

        # --- Proceed with fetching full results (for regular or --json output) ---
        results_data = []  # Store raw source data for JSON output
        results_hits = []  # Store hits for human-readable output

        search_params: Dict[str, Any] = {"index": history_index}
        # Use keyword field for filtering and sorting by group name
        group_field_keyword = "group_name.keyword"

        if group_filter:
            logger.info(
                f"Fetching history for group: {group_filter} using field '{group_field_keyword}'"
            )
            search_params["body"] = {
                "query": {"term": {group_field_keyword: group_filter}},
                "sort": [{"timestamp": "desc"}],
            }
            if show_all_history:
                search_params["size"] = 1000
                print(f"Fetching all history for group '{group_filter}'...")
            else:
                search_params["size"] = 1
                print(f"Fetching latest result for group '{group_filter}'...")

            response = db.instance.search(**search_params)
            results_hits = response["hits"]["hits"]

        elif show_all_history:
            logger.info(
                f"Fetching all history for all groups using field '{group_field_keyword}' for sorting."
            )
            print("Fetching all history entries for all groups...")
            search_params["body"] = {
                "query": {"match_all": {}},
                "sort": [{group_field_keyword: "asc"}, {"timestamp": "desc"}],
            }
            search_params["size"] = 10000
            logger.warning(
                "Fetching all history for all groups might return a large number of results."
            )

            response = db.instance.search(**search_params)
            results_hits = response["hits"]["hits"]

        else:  # Default: Latest result for each group
            logger.info(
                f"Fetching the latest result for each group using aggregation on field '{group_field_keyword}'."
            )
            print("Fetching latest result for each group...")
            search_params["body"] = {
                "size": 0,
                "aggs": {
                    "groups": {
                        "terms": {"field": group_field_keyword, "size": 1000},
                        "aggs": {
                            "latest_entry": {
                                "top_hits": {
                                    "size": 1,
                                    "sort": [{"timestamp": {"order": "desc"}}],
                                    "_source": {"includes": ["*"]},
                                }
                            }
                        },
                    }
                },
            }
            response = db.instance.search(**search_params)
            # Extract results from aggregation buckets
            temp_results = []
            for bucket in (
                response.get("aggregations", {}).get("groups", {}).get("buckets", [])
            ):
                latest_hit = (
                    bucket.get("latest_entry", {}).get("hits", {}).get("hits", [{}])[0]
                )
                if latest_hit:
                    temp_results.append(latest_hit)
            # Sort the final list by group name for consistent output order
            results_hits = sorted(
                temp_results, key=lambda x: x.get("_source", {}).get("group_name", "")
            )

        # --- Process and Print Results ---
        if not results_hits:
            if group_filter:
                print(f"No history found for group '{group_filter}'.")
            else:
                print(f"No history found in index '{history_index}'.")
        elif json_output:
            # Extract just the _source field for JSON output
            results_data = [hit.get("_source", {}) for hit in results_hits]
            print(json.dumps(results_data, indent=2))
        else:
            # Use the existing human-readable print function
            print(
                f"\n--- Grok Parsing History Results ({len(results_hits)} entries) ---"
            )
            for hit in results_hits:
                _print_result_entry(hit.get("_source", {}))
            print("\n--- End of Results ---")

    except NotFoundError:
        logger.error(f"History index '{history_index}' not found during search.")
        print(f"Error: Grok results history index '{history_index}' does not exist.")
    except Exception as e:
        logger.error(f"An error occurred during 'es-parse list': {e}", exc_info=True)
        import traceback

        traceback.print_exc()
        print(f"\nAn error occurred while fetching history: {e}")


# --- NEW Handler for 'use' subcommand ---
def handle_es_parse_use(args):
    """Handles the logic for the 'es-parse use' command."""
    target_group = args.group
    target_time_str = args.time  # User provides time string like "2025-04-08 18:19:56"
    history_index = cfg.INDEX_GROK_RESULTS_HISTORY
    # Format expected in the printout (must match _print_result_entry)
    EXPECTED_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    logger.info(
        f"Executing es-parse use: group='{target_group}', time='{target_time_str}'"
    )
    print(
        f"Attempting to re-run parsing for group '{target_group}' using pattern from run recorded around '{target_time_str}'..."
    )

    try:
        # --- Initialize DB ---
        db = ElasticsearchDatabase()
        if db.instance is None:
            logger.error("ES connection failed for 'use' command.")
            print("Error: Could not connect to Elasticsearch.")
            return

        if not db.instance.indices.exists(index=history_index):
            logger.error(
                f"History index '{history_index}' not found for 'use' command."
            )
            print(
                f"Error: Grok results history index '{history_index}' does not exist. Cannot find pattern."
            )
            return

        # --- Find the specific history entry ---
        # Query for all entries for the target group, sorted by time
        group_field_keyword = "group_name.keyword"
        query = {
            "query": {"term": {group_field_keyword: target_group}},
            "sort": [{"timestamp": "desc"}],
            "size": 1000,  # Fetch a reasonable number of recent entries
        }
        response = db.instance.search(index=history_index, body=query)
        hits = response["hits"]["hits"]

        found_entry = None
        found_pattern = None

        if not hits:
            logger.warning(f"No history found for group '{target_group}'.")
            print(f"Error: No history found for group '{target_group}'.")
            return

        # Iterate through hits and compare formatted timestamp
        for hit in hits:
            doc_source = hit.get("_source", {})
            timestamp_iso = doc_source.get("timestamp")
            if not timestamp_iso:
                continue

            try:
                dt_obj = datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
                formatted_time = dt_obj.strftime(EXPECTED_TIME_FORMAT)

                if formatted_time == target_time_str:
                    found_entry = doc_source
                    found_pattern = doc_source.get("grok_pattern_used")
                    logger.info(
                        f"Found matching history entry at {timestamp_iso} for group '{target_group}'."
                    )
                    break  # Stop searching once found
            except ValueError:
                logger.warning(
                    f"Could not parse timestamp {timestamp_iso} from history entry {hit.get('_id')}"
                )
                continue  # Skip entry if timestamp is invalid

        if not found_entry:
            logger.error(
                f"Could not find history entry for group '{target_group}' matching time '{target_time_str}'."
            )
            print(
                f"Error: Could not find a history entry for group '{target_group}' recorded at '{target_time_str}'. Check 'list' output."
            )
            return

        if not found_pattern or found_pattern == "N/A":
            logger.error(
                f"History entry found, but no valid 'grok_pattern_used' field: {found_pattern}"
            )
            print(
                f"Error: History entry found, but it does not contain a valid Grok pattern to use."
            )
            return

        logger.info(f"Using Grok pattern from history: {found_pattern}")
        print(f"Found pattern from history: {found_pattern}")

        # --- Re-run parsing using the found pattern ---
        print("\nRe-running parsing with the historical pattern...")

        # Initialize other dependencies needed for the agent run
        model = GeminiModel()
        json_file_path = getattr(args, "json", None) or (
            "prompts/test.json"
            if getattr(args, "test", False)
            else "prompts/prompts.json"
        )
        prompts_manager = PromptsManager(json_file=json_file_path)

        agent = SingleGroupParserAgent(
            model=model, db=db, prompts_manager=prompts_manager
        )

        # Prepare config, forcing the historical pattern and using defaults for others
        # We force the pattern, validation runs but won't trigger retries if it fails.
        single_group_config: Dict[str, Any] = {
            "group_name": target_group,
            "field_to_parse": args.field
            or "content",  # Use default or CLI arg if provided
            "fields_to_copy": args.copy_fields or None,  # Use default or CLI arg
            "batch_size": args.batch_size or 1000,  # Use default or CLI arg
            "sample_size_generation": 0,  # Not needed
            "sample_size_validation": args.validation_sample_size
            or 10,  # Keep validation sample size
            "validation_threshold": 0.5,  # Set threshold impossible to meet to prevent re-generation on validation failure
            "max_regeneration_attempts": 1,  # Only 1 attempt (no regeneration)
            "provided_grok_pattern": found_pattern,  # FORCE the historical pattern
            "keep_unparsed_index": args.keep_unparsed
            or False,  # Use default or CLI arg
        }

        # Run the agent
        final_group_state: SingleGroupParseGraphState | Dict[str, Any] = agent.run(
            single_group_config
        )

        # --- Display Summary (same logic as single group in handle_es_parse) ---
        print("\n--- Elasticsearch Parsing Summary ('use' command) ---")
        status = final_group_state.get("final_parsing_status", "unknown")
        results_summary = final_group_state.get("final_parsing_results_summary")
        error_msgs = final_group_state.get("error_messages", [])

        pattern_used = final_group_state.get(
            "current_grok_pattern", "N/A"
        )  # Should be the historical one
        # Fallback status shouldn't occur here normally, but handle just in case
        if status == "success_fallback":
            pattern_used = "Fallback: " + SingleGroupParserAgent.FALLBACK_PATTERN
        elif "failed" in status:
            pattern_used = f"Failed (Pattern Used: {found_pattern})"

        processed = results_summary.get("processed", 0) if results_summary else 0
        indexed_ok = results_summary.get("successful", 0) if results_summary else 0
        indexed_failed_fallback = (
            results_summary.get("failed", 0) if results_summary else 0
        )
        parse_errors = results_summary.get("parse_errors", 0) if results_summary else 0
        index_errors = results_summary.get("index_errors", 0) if results_summary else 0

        target_idx_name = cfg.get_parsed_log_storage_index(target_group)
        failed_idx_name = cfg.get_unparsed_log_storage_index(target_group)

        print(f"\nGroup '{target_group}':")
        print(f"  Status: {status}")
        print(f"  Pattern Used (from history): {pattern_used}")
        print(f"  Docs Scanned: {processed}")
        print(
            f"  Indexed Successfully (-> {os.path.basename(target_idx_name)}): {indexed_ok}"
        )
        print(
            f"  Failed/Fallback (-> {os.path.basename(failed_idx_name)}): {indexed_failed_fallback}"
        )
        print(f"  Grok Parse Errors (within run): {parse_errors}")
        print(f"  Bulk Indexing Errors: {index_errors}")

        if error_msgs:
            print("  Agent Errors/Warnings:")
            for i, msg in enumerate(error_msgs[:5]):
                print(f"    - {msg}")
            if len(error_msgs) > 5:
                print("    ...")

        if status in ["success", "success_with_errors"]:
            if parse_errors == 0 and index_errors == 0 and not error_msgs:
                print("\nResult: SUCCESSFUL")
            else:
                print("\nResult: COMPLETED WITH ERRORS/FAILURES")
        else:
            print("\nResult: FAILED")

        logger.info(
            f"'es-parse use' finished for group '{target_group}'. Final Status: {status}"
        )

    except Exception as e:
        logger.error(
            f"An critical error occurred during 'es-parse use': {e}", exc_info=True
        )
        print(f"\nAn critical error occurred: {e}")
        import traceback

        traceback.print_exc()


# --- Updated register_es_parse_parser ---
def register_es_parse_parser(subparsers):
    """Registers the 'es-parse' command and its subcommands."""
    es_parse_parser = subparsers.add_parser(
        "es-parse",
        help="Parse logs in ES using Grok, list past results, or re-run with historical pattern",  # Updated help
        description="Processes logs stored in Elasticsearch using Grok patterns, lists results, or uses a previous pattern.",  # Updated desc
    )
    es_parse_subparsers = es_parse_parser.add_subparsers(
        dest="es_parse_action", help="ES Parsing action (run, list, use)", required=True
    )

    # --- 'run' Subcommand (Inherits most arguments) ---
    run_parser = es_parse_subparsers.add_parser(
        "run",
        help="Run the Grok parsing process on ES logs",
        description="Retrieves logs, generates/validates Grok patterns, parses logs, and indexes results.",
    )
    # Add arguments common to 'run' and 'use' here, others specific below
    run_parser.add_argument(
        "-g",
        "--group",
        type=str,
        default=None,
        help="(Optional for run, Required for use) Specify a single group name.",
    )

    run_parser.add_argument(
        "-f",
        "--field",
        type=str,
        default="content",
        help="Source field containing the raw log line (default: content).",
    )

    run_parser.add_argument(
        "--copy-fields",
        type=str,
        nargs="*",
        help="(Optional) Additional source fields to copy to the target document.",
    )

    run_parser.add_argument(
        "-b",
        "--batch-size",
        type=int,
        default=1000,
        help="Documents to process/index per batch (default: 1000).",
    )

    run_parser.add_argument(
        "--keep-unparsed",
        action="store_true",
        help="Do not delete the unparsed log index before running.",
    )

    # Arguments specific to 'run'
    run_parser.add_argument(
        "-s",
        "--sample-size",
        type=int,
        default=20,
        help="Log lines to sample for LLM Grok pattern generation (default: 20).",
    )

    run_parser.add_argument(
        "--validation-sample-size",
        type=int,
        default=10,
        help="Number of lines for validating a generated Grok pattern (default: 10).",
    )

    run_parser.add_argument(
        "--validation-threshold",
        type=float,
        default=0.5,
        help="Minimum success rate (0.0-1.0) on validation sample to accept Grok pattern (default: 0.5).",
    )

    run_parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Maximum number of times to retry Grok pattern generation if validation fails (default: 2).",
    )

    default_threads = 1
    try:
        max_threads = multiprocessing.cpu_count()
        max_help = f"Max suggest: {max_threads}"
    except NotImplementedError:
        max_threads = 1
        max_help = "Cannot determine max CPUs"

    run_parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=default_threads,
        help=f"Parallel workers for ALL groups (ignored for single group). Default: {default_threads}. {max_help}",
    )

    run_parser.add_argument(
        "-p",
        "--pattern",
        type=str,
        default=None,
        help="Provide a specific Grok pattern string to use for parsing. Requires --group to be specified.",
    )

    run_parser.set_defaults(func=handle_es_parse)

    # --- 'list' Subcommand ---
    list_parser = es_parse_subparsers.add_parser(
        "list",
        help="List results from previous es-parse runs",
        description=f"Queries the '{cfg.INDEX_GROK_RESULTS_HISTORY}' index to show past Grok parsing results.",
    )

    list_parser.add_argument(
        "-g",
        "--group",
        type=str,
        default=None,
        help="(Optional) Show results only for a specific group name.",
    )

    list_parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Show all historical results for the selected group(s), instead of just the latest.",
    )

    list_parser.add_argument(
        "--group-name",
        action="store_true",
        help="List only the names of groups found in the history.",
    )

    list_parser.add_argument(
        "--json",
        action="store_true",  # Changed from '-j' to avoid conflict with global -j
        help="Output the results in JSON format.",
    )

    list_parser.set_defaults(func=handle_es_parse_list)

    # --- 'use' Subcommand (NEW) ---

    use_parser = es_parse_subparsers.add_parser(
        "use",
        help="Re-run parsing for a group using a pattern from a specific past run",
        description="Finds a historical run by group and time, extracts the pattern, and re-runs parsing for that group.",
    )

    use_parser.add_argument(
        "-g",
        "--group",
        type=str,
        required=True,  # Group is required for 'use'
        help="The group name to re-run parsing for.",
    )

    use_parser.add_argument(
        "-t",
        "--time",
        type=str,
        required=True,
        help='Timestamp string (e.g., "2025-04-08 18:19:56") of the historical run to use the pattern from (copy from `list` output).',
    )

    # Add common optional args that might be useful to override defaults during 'use'
    use_parser.add_argument(
        "-f",
        "--field",
        type=str,  # Default comes from handle_es_parse_use
        help="(Optional) Override source field containing the raw log line (default: content).",
    )

    use_parser.add_argument(
        "--copy-fields",
        type=str,
        nargs="*",  # Default comes from handle_es_parse_use
        help="(Optional) Override additional source fields to copy.",
    )

    use_parser.add_argument(
        "-b",
        "--batch-size",
        type=int,  # Default comes from handle_es_parse_use
        help="(Optional) Override documents per batch (default: 1000).",
    )

    use_parser.add_argument(
        "--validation-sample-size",
        type=int,  # Default comes from handle_es_parse_use
        help="(Optional) Override validation sample size (default: 10).",
    )

    use_parser.add_argument(
        "--keep-unparsed",
        action="store_true",  # Default comes from handle_es_parse_use
        help="(Optional) Do not delete the unparsed log index before running.",
    )

    use_parser.set_defaults(func=handle_es_parse_use)
