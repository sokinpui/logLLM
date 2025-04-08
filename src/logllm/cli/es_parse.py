# src/logllm/cli/es_parse.py

import argparse
import sys
import multiprocessing
import os # Import os for path manipulation if needed
from typing import Dict, Any
from datetime import datetime
from elasticsearch import NotFoundError

try:
    # Import agents - paths might need adjustment based on final structure
    # The main agents used here are AllGroupsParserAgent and SingleGroupParserAgent
    from ..agents.es_parser_agent import (
        AllGroupsParserAgent,
        SingleGroupParserAgent,
        AllGroupsParserState, # State for the orchestrator
        SingleGroupParseGraphState # Final state returned for each group
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

def handle_es_parse(args):
    """Handles the logic for the 'es-parse' command using the new agents."""
    num_threads = args.threads
    batch_size = args.batch_size
    sample_size = args.sample_size # Used for generation
    target_group = args.group
    field_to_parse = args.field
    fields_to_copy = args.copy_fields
    provided_pattern = args.pattern

    # --- Get new config options from args ---
    validation_sample_size = args.validation_sample_size
    validation_threshold = args.validation_threshold
    max_regeneration_attempts = args.max_retries # Renamed arg

    # --- Validate Inputs ---
    if num_threads < 1: num_threads = 1
    if batch_size < 1: batch_size = 5000
    if sample_size < 1: sample_size = 10
    if validation_sample_size < 1: validation_sample_size = 10
    if not (0.0 <= validation_threshold <= 1.0): validation_threshold = 0.5
    if max_regeneration_attempts < 0: max_regeneration_attempts = 0 # 0 retries means 1 attempt

    if provided_pattern and not target_group:
        msg = "The --pattern argument requires the --group argument to be specified."
        logger.error(msg)
        print(f"Error: {msg}")
        sys.exit(1)

    # Log execution mode
    if target_group:
        effective_num_threads = 1
        logger.info(f"Executing ES parse for SINGLE group: '{target_group}'. Batch: {batch_size}, GenSample: {sample_size}, ValSample: {validation_sample_size}, Retries: {max_regeneration_attempts}")
        print(f"Starting ES log parsing for SINGLE group: '{target_group}'.")
    else:
        effective_num_threads = num_threads
        logger.info(f"Executing ES parse for ALL groups. Workers: {effective_num_threads}, Batch: {batch_size}, GenSample: {sample_size}, ValSample: {validation_sample_size}, Retries: {max_regeneration_attempts}")
        print(f"Starting ES log parsing for ALL groups. Workers: {effective_num_threads}")

    try:
        # --- Initialize Dependencies (Common) ---
        logger.info("Initializing components for Elasticsearch parsing...")
        db = ElasticsearchDatabase()
        if db.instance is None:
             logger.error("Elasticsearch connection failed. Cannot proceed."); print("Error: Could not connect to Elasticsearch."); return

        model = GeminiModel() # Ensure API key is set
        json_file_path = getattr(args, 'json', None) or ("prompts/test.json" if getattr(args, 'test', False) else "prompts/prompts.json")
        prompts_manager = PromptsManager(json_file=json_file_path)

        # --- Branch Logic: Single Group vs All Groups ---

        if target_group:
            # --- SINGLE GROUP Parsing ---
            logger.info(f"Instantiating SingleGroupParserAgent for group '{target_group}'")
            agent = SingleGroupParserAgent(model=model, db=db, prompts_manager=prompts_manager)

            # Prepare the config dictionary for the agent's run method
            single_group_config: Dict[str, Any] = {
                "group_name": target_group,
                "field_to_parse": field_to_parse,
                "fields_to_copy": fields_to_copy,
                "batch_size": batch_size,
                "sample_size_generation": sample_size, # Map arg to state key
                "sample_size_validation": validation_sample_size,
                "validation_threshold": validation_threshold,
                "max_regeneration_attempts": max_regeneration_attempts + 1, # Agent expects max *attempts*
                "provided_grok_pattern": provided_pattern
            }

            # Run the agent (which executes its internal graph)
            final_group_state: SingleGroupParseGraphState | Dict[str, Any] = agent.run(single_group_config)

            # --- Display Summary (Single Group - using new state) ---
            print("\n--- Elasticsearch Parsing Summary (Single Group) ---")
            status = final_group_state.get("final_parsing_status", "unknown")
            # Use the summary dictionary now
            results_summary = final_group_state.get("final_parsing_results_summary")
            error_msgs = final_group_state.get("error_messages", [])

            pattern_used = final_group_state.get("current_grok_pattern", "N/A")
            if status == "success_fallback": pattern_used = "Fallback: " + SingleGroupParserAgent.FALLBACK_PATTERN
            elif status == "failed_fallback": pattern_used = "Fallback FAILED"
            elif "failed" in status: pattern_used = "Failed before/during parsing"
            elif not pattern_used or pattern_used == "N/A": pattern_used = "Pattern Generation/Validation Failed"

            # Extract counts from the summary dict
            processed = results_summary.get("processed", 0) if results_summary else 0
            indexed_ok = results_summary.get("successful", 0) if results_summary else 0
            indexed_failed_fallback = results_summary.get("failed", 0) if results_summary else 0 # Docs sent to failed index
            parse_errors = results_summary.get("parse_errors", 0) if results_summary else 0 # Grok mismatches
            index_errors = results_summary.get("index_errors", 0) if results_summary else 0 # Bulk API errors

            target_idx_name = cfg.get_parsed_log_storage_index(target_group)
            failed_idx_name = cfg.get_unparsed_log_storage_index(target_group)

            print(f"\nGroup '{target_group}':")
            print(f"  Status: {status}")
            print(f"  Pattern Detail: {pattern_used}")
            print(f"  Docs Scanned: {processed}")
            print(f"  Indexed Successfully (-> {os.path.basename(target_idx_name)}): {indexed_ok}")
            print(f"  Failed/Fallback (-> {os.path.basename(failed_idx_name)}): {indexed_failed_fallback}")
            print(f"  Grok Parse Errors (within run): {parse_errors}")
            print(f"  Bulk Indexing Errors: {index_errors}")

            if error_msgs:
                print("  Agent Errors/Warnings:")
                for i, msg in enumerate(error_msgs[:5]): print(f"    - {msg}")
                if len(error_msgs) > 5: print("    ...")

            if status in ["success", "success_with_errors", "success_fallback"]:
                 if parse_errors == 0 and index_errors == 0 and not error_msgs: print("\nResult: SUCCESSFUL (details above)")
                 else: print("\nResult: COMPLETED WITH ERRORS/FAILURES (details above)")
            else:
                 print("\nResult: FAILED")

            logger.info(f"Single group ('{target_group}') parsing finished. Final Status: {status}")

        else:
            # --- ALL GROUPS Parsing ---
            logger.info("Instantiating AllGroupsParserAgent")
            # AllGroupsParserAgent now internally uses the new SingleGroupParserAgent logic via the worker
            agent = AllGroupsParserAgent(model=model, db=db, prompts_manager=prompts_manager)

            initial_orchestrator_state: AllGroupsParserState = {
                "group_info_index": cfg.INDEX_GROUP_INFOS,
                "field_to_parse": field_to_parse,
                "fields_to_copy": fields_to_copy,
                "group_results": {}, # Will be populated with SingleGroupParseGraphState
                "status": "pending"
            }

            # Run the orchestrator agent, passing necessary parameters for the worker/single agent
            final_orchestrator_state = agent.run(
                initial_state=initial_orchestrator_state,
                num_threads=effective_num_threads,
                batch_size=batch_size,
                sample_size=sample_size, # For generation sample size
                # --- Pass new parameters down ---
                validation_sample_size=validation_sample_size,
                validation_threshold=validation_threshold,
                max_regeneration_attempts=max_regeneration_attempts + 1 # Agent expects max attempts
            )

            # --- Display Summary (All Groups - using new state) ---
            print("\n--- Elasticsearch Parsing Summary (All Groups) ---")
            if final_orchestrator_state["status"] == "completed":
                group_results_dict = final_orchestrator_state.get("group_results", {})
                total_groups = len(group_results_dict)
                success_count = 0           # Status = "success"
                success_errors_count = 0    # Status = "success_with_errors"
                fallback_count = 0          # Status = "success_fallback"
                failed_count = 0            # Status contains "failed"

                total_processed_all = 0
                total_indexed_ok_all = 0
                total_indexed_failed_fallback_all = 0
                total_parse_errors_all = 0
                total_index_errors_all = 0

                print(f"Processed {total_groups} groups.")

                for group_name, group_final_state in group_results_dict.items():
                     status = group_final_state.get("final_parsing_status", "unknown")
                     results_summary = group_final_state.get("final_parsing_results_summary")
                     error_msgs = group_final_state.get("error_messages", [])

                     pattern_used = group_final_state.get("current_grok_pattern", "N/A") # Last attempted/used
                     if status == "success_fallback": pattern_used = "Fallback: " + SingleGroupParserAgent.FALLBACK_PATTERN
                     elif "failed" in status: pattern_used = f"Failed (see logs)"
                     elif not pattern_used: pattern_used = "N/A (Generation/Validation Failed)"

                     processed = results_summary.get("processed", 0) if results_summary else 0
                     indexed_ok = results_summary.get("successful", 0) if results_summary else 0
                     indexed_failed_fallback = results_summary.get("failed", 0) if results_summary else 0
                     parse_errors = results_summary.get("parse_errors", 0) if results_summary else 0
                     index_errors = results_summary.get("index_errors", 0) if results_summary else 0

                     target_idx_name = cfg.get_parsed_log_storage_index(group_name)
                     failed_idx_name = cfg.get_unparsed_log_storage_index(group_name)

                     print(f"\nGroup '{group_name}':")
                     print(f"  Status: {status}")
                     print(f"  Pattern Detail: {pattern_used}")
                     print(f"  Docs Scanned: {processed}")
                     print(f"  Indexed Successfully (-> {os.path.basename(target_idx_name)}): {indexed_ok}")
                     print(f"  Failed/Fallback (-> {os.path.basename(failed_idx_name)}): {indexed_failed_fallback}")
                     print(f"  Grok Parse Errors: {parse_errors}, Bulk Index Errors: {index_errors}")
                     if error_msgs: print(f"  Agent Errors/Warnings: {len(error_msgs)} (See logs)")

                     # Update overall counters based on status
                     if status == "success": success_count += 1
                     elif status == "success_with_errors": success_errors_count += 1
                     elif status == "success_fallback": fallback_count += 1
                     else: failed_count += 1 # Count all failure types together

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
                print(f"Total Successfully Indexed (Target Indices): {total_indexed_ok_all}")
                print(f"Total Failed/Fallback Indexed (Failed Indices): {total_indexed_failed_fallback_all}")
                print(f"Total Grok Parse Errors: {total_parse_errors_all}")
                print(f"Total Bulk Indexing Errors: {total_index_errors_all}")

            else: # Orchestrator status not 'completed'
                print(f"Overall Status: FAILED ({final_orchestrator_state.get('status', 'unknown')})")
                print("Check logs for detailed errors during orchestration.")

            logger.info("All groups parsing finished.")

    except Exception as e:
        logger.error(f"An critical error occurred during es-parse execution: {e}", exc_info=True)
        print(f"\nAn critical error occurred: {e}")
        import traceback
        traceback.print_exc()

def _print_result_entry(doc_source: dict):
    """Formats and prints a single entry from the grok_results_history index."""
    group = doc_source.get("group_name", "N/A")
    status = doc_source.get("parsing_status", "unknown")
    pattern = doc_source.get("grok_pattern_used", "N/A")
    timestamp_iso = doc_source.get("timestamp")
    processed = doc_source.get("processed_count", 0)
    successful = doc_source.get("successful_count", 0)
    failed = doc_source.get("failed_count", 0) # Docs in failed index
    parse_errors = doc_source.get("parse_error_count", 0) # Grok mismatches
    index_errors = doc_source.get("index_error_count", 0) # Bulk errors
    agent_errors = doc_source.get("agent_error_count", 0)

    # Format timestamp
    try:
        if timestamp_iso:
            dt_obj = datetime.fromisoformat(timestamp_iso)
            timestamp_str = dt_obj.strftime("%Y-%m-%d %H:%M:%S %Z") # Example format
        else:
            timestamp_str = "N/A"
    except ValueError:
        timestamp_str = f"Invalid ({timestamp_iso})"

    target_idx_name = cfg.get_parsed_log_storage_index(group)
    # Use the RENAMED function for the unparsed index name
    unparsed_idx_name = cfg.get_unparsed_log_storage_index(group)

    print(f"\nGroup '{group}' (Recorded: {timestamp_str}):")
    print(f"  Status: {status}")
    print(f"  Pattern Detail: {pattern}")
    print(f"  Docs Scanned: {processed}")
    print(f"  Indexed Successfully (-> {os.path.basename(target_idx_name)}): {successful}")
    # Updated print statement using the RENAMED config function name
    print(f"  Failed/Fallback (-> {os.path.basename(unparsed_idx_name)}): {failed}")
    print(f"  Grok Parse Errors: {parse_errors}, Bulk Index Errors: {index_errors}")
    if agent_errors > 0:
        print(f"  Agent Errors/Warnings: {agent_errors} (See logs for details)")

# --- Handler for 'list' subcommand ---
def handle_es_parse_list(args):
    """Handles the logic for the 'es-parse list' command."""
    logger.info(f"Executing es-parse list: group={args.group}, all_history={args.all}")
    group_filter = args.group
    show_all_history = args.all
    history_index = cfg.INDEX_GROK_RESULTS_HISTORY

    try:
        db = ElasticsearchDatabase()
        if db.instance is None:
             logger.error("ES connection failed for listing results.")
             print("Error: Could not connect to Elasticsearch.")
             return

        if not db.instance.indices.exists(index=history_index):
            logger.warning(f"History index '{history_index}' not found.")
            print(f"Error: Grok results history index '{history_index}' does not exist. Run 'es-parse run' first.")
            return

        results = []
        search_params: Dict[str, Any] = {"index": history_index} # Type hint for clarity

        # --- Determine the correct field name ---
        group_field_name = "group_name" if group_filter and '.' in group_filter else "group_name.keyword"
        # ----------------------------------------

        if group_filter:
            # --- Filter by Specific Group ---
            logger.info(f"Fetching history for group: {group_filter} using field '{group_field_name}'")
            search_params["body"] = {
                # *** FIX HERE: Use the variable's value as the key ***
                "query": {"term": {group_field_name: group_filter}},
                "sort": [{"timestamp": "desc"}]
            }
            if show_all_history:
                search_params["size"] = 1000
                print(f"Fetching all history for group '{group_filter}'...")
            else:
                search_params["size"] = 1
                print(f"Fetching latest result for group '{group_filter}'...")

            response = db.instance.search(**search_params)
            results = response['hits']['hits']

        elif show_all_history:
            # --- Fetch All History for All Groups ---
            logger.info(f"Fetching all history for all groups using field '{group_field_name}' for sorting.")
            print("Fetching all history entries for all groups...")
            search_params["body"] = {
                "query": {"match_all": {}},
                # *** FIX HERE: Use the variable's value as the key ***
                "sort": [
                    {group_field_name: "asc"},
                    {"timestamp": "desc"}
                ]
            }
            search_params["size"] = 10000
            logger.warning("Fetching all history for all groups might return a large number of results.")

            response = db.instance.search(**search_params)
            results = response['hits']['hits']

        else:
            # --- Fetch Latest Result for Each Group (Default) ---
            logger.info(f"Fetching the latest result for each group using aggregation on field '{group_field_name}'.")
            print("Fetching latest result for each group...")
            search_params["body"] = {
              "size": 0,
              "aggs": {
                "groups": {
                  # *** FIX HERE: Use the variable's value for the field parameter ***
                  "terms": {"field": group_field_name, "size": 1000},
                  "aggs": {
                    "latest_entry": {
                      "top_hits": {
                        "size": 1,
                        "sort": [{"timestamp": {"order": "desc"}}],
                        "_source": {"includes": ["*"]}
                      }
                    }
                  }
                }
              }
            }
            response = db.instance.search(**search_params)
            # Extract results from aggregation buckets
            results = [] # Ensure results is reset here
            for bucket in response.get('aggregations', {}).get('groups', {}).get('buckets', []):
                 latest_hit = bucket.get('latest_entry', {}).get('hits', {}).get('hits', [{}])[0]
                 if latest_hit:
                     results.append(latest_hit)
            # Sort the final list by group name for consistent output order
            results.sort(key=lambda x: x.get('_source', {}).get('group_name', ''))

        # --- Print Results ---
        if not results:
            if group_filter: print(f"No history found for group '{group_filter}'.")
            else: print(f"No history found in index '{history_index}'.")
        else:
            print(f"\n--- Grok Parsing History Results ({len(results)} entries) ---")
            for hit in results:
                 _print_result_entry(hit.get('_source', {}))
            print("\n--- End of Results ---")

    except NotFoundError:
        logger.error(f"History index '{history_index}' not found during search.")
        print(f"Error: Grok results history index '{history_index}' does not exist.")
    except Exception as e:
        logger.error(f"An error occurred during 'es-parse list': {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        print(f"\nAn error occurred while fetching history: {e}")

def register_es_parse_parser(subparsers):
    """Registers the 'es-parse' command and its subcommands."""
    es_parse_parser = subparsers.add_parser(
        'es-parse',
        help='Parse logs in ES using Grok or list past results', # Updated help
        description="Processes logs stored in Elasticsearch using Grok patterns with validation and retries, or lists the results of previous runs." # Updated desc
    )
    es_parse_subparsers = es_parse_parser.add_subparsers(
        dest='es_parse_action', help='ES Parsing action (run or list)', required=True
        )

    # --- 'run' Subcommand (The original parsing logic) ---
    run_parser = es_parse_subparsers.add_parser(
        'run',
        help='Run the Grok parsing process on ES logs',
        description="Retrieves logs from source indices, generates/validates Grok patterns, parses logs, and indexes results."
    )

    # (Add all the arguments from the original es_parse_parser here)
    run_parser.add_argument(
            '-g', '--group', type=str, default=None,
            help='(Optional) Specify a single group name to parse. If omitted, all groups are processed.'
    )

    run_parser.add_argument(
            '-f', '--field', type=str, default='content',
            help='Source field containing the raw log line (default: content).'
    )

    run_parser.add_argument(
            '--copy-fields', type=str, nargs='*',
            help='(Optional) Additional source fields to copy to the target document.'
    )

    run_parser.add_argument(
            '-b', '--batch-size', type=int, default=5000,
            help='Documents to process/index per batch (default: 5000).'
    )

    run_parser.add_argument(
            '-s', '--sample-size', type=int, default=20,
            help='Log lines to sample for LLM Grok pattern generation (default: 20).'
    )

    run_parser.add_argument(
            '--validation-sample-size', type=int, default=10,
            help='Number of lines for validating a generated Grok pattern (default: 10).'
    )

    run_parser.add_argument(
            '--validation-threshold', type=float, default=0.5,
            help='Minimum success rate (0.0-1.0) on validation sample to accept Grok pattern (default: 0.5).'
    )

    run_parser.add_argument(
            '--max-retries', type=int, default=2,
            help='Maximum number of times to retry Grok pattern generation if validation fails (default: 2).'
    )

    default_threads = 1
    try:
        max_threads = multiprocessing.cpu_count()
        max_help = f"Max suggest: {max_threads}"
    except NotImplementedError:
        max_threads = 1
        max_help = "Cannot determine max CPUs"

    run_parser.add_argument(
            '-t', '--threads', type=int, default=default_threads,
            help=f'Parallel workers for ALL groups (ignored for single group). Default: {default_threads}. {max_help}'
    )

    run_parser.add_argument(
        '-p', '--pattern', type=str, default=None,
        help='Provide a specific Grok pattern string to use for parsing. Requires --group to be specified.'
    )

    run_parser.set_defaults(func=handle_es_parse) # Point 'run' action to the original handler

    # --- 'list' Subcommand (NEW) ---
    list_parser = es_parse_subparsers.add_parser(
        'list',
        help='List results from previous es-parse runs',
        description=f"Queries the '{cfg.INDEX_GROK_RESULTS_HISTORY}' index to show past Grok parsing results. By default shows the latest result for each group."
    )

    list_parser.add_argument(
        '-g', '--group', type=str, default=None,
        help='(Optional) Show results only for a specific group name.'
    )

    list_parser.add_argument(
        '-a', '--all', action='store_true',
        help='Show all historical results for the selected group(s), instead of just the latest.'
    )
    list_parser.set_defaults(func=handle_es_parse_list) # Point 'list' action to the new handler
