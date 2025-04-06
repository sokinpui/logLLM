# src/logllm/cli/es_parse.py

import argparse
import sys
import multiprocessing

try:
    # Import both agents now, as handle_es_parse might use either
    from ..agents.es_parser_agent import (
        AllGroupsParserAgent,
        SingleGroupParserAgent,
        AllGroupsParserState,
        SingleGroupParserState
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
    """Handles the logic for the 'es-parse' command."""
    num_threads = args.threads
    batch_size = args.batch_size
    sample_size = args.sample_size
    target_group = args.group # <--- Get the specific group name, if provided

    # --- Validate Inputs ---
    if num_threads < 1:
        logger.warning(f"Invalid thread count ({num_threads}) specified. Defaulting to 1.")
        num_threads = 1
    if batch_size < 1:
        logger.warning(f"Invalid batch size ({batch_size}) specified. Defaulting to 5000.")
        batch_size = 5000
    if sample_size < 1:
        logger.warning(f"Invalid sample size ({sample_size}) specified. Defaulting to 20.")
        sample_size = 20

    # Log execution mode
    if target_group:
        # Ignore threads for single group parsing (it runs sequentially within the group anyway)
        if num_threads > 1:
            logger.warning(f"Ignoring --threads ({num_threads}) when parsing a single group ('{target_group}').")
        effective_num_threads = 1
        logger.info(f"Executing Elasticsearch parse command for SINGLE group: '{target_group}'. Batch Size: {batch_size}, Sample Size: {sample_size}")
        print(f"Starting Elasticsearch log parsing for SINGLE group: '{target_group}'. Batch Size: {batch_size}, Sample Size: {sample_size}")
    else:
        effective_num_threads = num_threads
        logger.info(f"Executing Elasticsearch parse command for ALL groups. Workers: {effective_num_threads}, Batch Size: {batch_size}, Sample Size: {sample_size}")
        print(f"Starting Elasticsearch log parsing for ALL groups. Workers: {effective_num_threads}, Batch Size: {batch_size}, Sample Size: {sample_size}")


    try:
        # --- Initialize Dependencies (Common) ---
        logger.info("Initializing components for Elasticsearch parsing...")
        db = ElasticsearchDatabase()
        if db.instance is None:
             logger.error("Elasticsearch connection failed. Cannot proceed.")
             print("Error: Could not connect to Elasticsearch.")
             return

        model = GeminiModel()
        json_file = getattr(args, 'json', None) or ("prompts/test.json" if getattr(args, 'test', False) else "prompts/prompts.json")
        prompts_manager = PromptsManager(json_file=json_file)

        # --- Branch Logic: Single Group vs All Groups ---

        if target_group:
            # --- SINGLE GROUP Parsing ---
            logger.info(f"Instantiating SingleGroupParserAgent for group '{target_group}'")
            agent = SingleGroupParserAgent(model=model, db=db, prompts_manager=prompts_manager)

            # Prepare state for the single group
            initial_group_state: SingleGroupParserState = {
                "group_name": target_group,
                "field_to_parse": args.field,
                "fields_to_copy": args.copy_fields,
                "batch_size": batch_size,
                "sample_size": sample_size,
                # Set defaults
                "group_id_field": None, "group_id_value": None, "source_index": "", "target_index": "",
                "generated_grok_pattern": None, "parsing_status": "pending", "parsing_result": None
            }

            # Run the agent for the single group
            final_group_state = agent.run(initial_group_state)

            # Display Summary for single group
            print("\n--- Elasticsearch Parsing Summary (Single Group) ---")
            status = final_group_state.get("parsing_status", "unknown")
            pattern = final_group_state.get("generated_grok_pattern", "N/A")
            parse_result = final_group_state.get("parsing_result")
            processed = parse_result.get("processed_count", 0) if parse_result else 0
            indexed = parse_result.get("indexed_count", 0) if parse_result else 0
            errors = parse_result.get("error_count", 0) if parse_result else 0

            print(f"\nGroup '{target_group}':")
            print(f"  Status: {status}")
            print(f"  Grok Pattern Used: {pattern}")
            print(f"  Docs Scanned: {processed}, Docs Indexed: {indexed}, Errors: {errors}")

            if status == "completed" and errors == 0:
                print("\nResult: SUCCESS")
            else:
                print("\nResult: FAILED (or completed with errors)")
            logger.info(f"Single group ('{target_group}') parsing finished. Status: {status}")

        else:
            # --- ALL GROUPS Parsing (Existing Logic) ---
            logger.info("Instantiating AllGroupsParserAgent")
            agent = AllGroupsParserAgent(model=model, db=db, prompts_manager=prompts_manager)

            initial_state: AllGroupsParserState = {
                "group_info_index": cfg.INDEX_GROUP_INFOS,
                "field_to_parse": args.field,
                "fields_to_copy": args.copy_fields,
                "group_results": {},
                "status": "pending"
            }

            # Run the agent for all groups
            final_state = agent.run(
                initial_state=initial_state,
                num_threads=effective_num_threads, # Pass effective number (might be 1)
                batch_size=batch_size,
                sample_size=sample_size
            )

            # Display Summary for all groups (Existing Logic)
            print("\n--- Elasticsearch Parsing Summary (All Groups) ---")
            if final_state["status"] == "completed":
                total_groups = len(final_state.get("group_results", {}))
                successful_groups = 0
                total_docs_processed = 0
                total_docs_indexed = 0
                total_errors = 0
                print(f"Processed {total_groups} groups.")

                for group_name, group_result in final_state.get("group_results", {}).items():
                     status = group_result.get("parsing_status", "unknown")
                     pattern = group_result.get("generated_grok_pattern", "N/A")
                     parse_result = group_result.get("parsing_result")
                     fallback = group_result.get("fallback_used", False) # Get fallback flag
                     processed = parse_result.get("processed_count", 0) if parse_result else 0
                     indexed = parse_result.get("indexed_count", 0) if parse_result else 0
                     errors = parse_result.get("error_count", 0) if parse_result else 0

                     print(f"\nGroup '{group_name}':")
                     print(f"  Status: {status}{' (Fallback Used)' if fallback else ''}") # Indicate fallback
                     # Only show generated pattern if fallback wasn't used or it was generated before fallback
                     if pattern != "N/A" and not fallback:
                        print(f"  Generated Grok Pattern: {pattern}")
                     elif fallback:
                        print(f"  Original Pattern Failed (Fallback: %{{GREEDYDATA:message}})")
                     else:
                        print(f"  Pattern Generation Failed") # If pattern is N/A and fallback wasn't explicitly used

                     print(f"  Docs Scanned: {processed}, Docs Indexed: {indexed}, Errors: {errors}")

                     if status == "completed" and errors == 0:
                          successful_groups += 1
                     total_docs_processed += processed
                     total_docs_indexed += indexed
                     total_errors += errors

                print("\n--- Overall ---")
                print(f"Successfully Parsed Groups: {successful_groups}/{total_groups}")
                print(f"Total Documents Scanned (across all groups): {total_docs_processed}")
                print(f"Total Documents Successfully Indexed: {total_docs_indexed}")
                print(f"Total Errors (parsing + indexing): {total_errors}")
            else:
                print("Overall Status: FAILED")
                print("Check logs for detailed errors during orchestration or group processing.")

            logger.info("All groups parsing finished.")

    except Exception as e:
        logger.error(f"An critical error occurred during es-parse execution: {e}", exc_info=True)
        print(f"\nAn critical error occurred: {e}")
        import traceback
        traceback.print_exc()


def register_es_parse_parser(subparsers):
    """Registers the 'es-parse' command and its arguments."""
    es_parse_parser = subparsers.add_parser(
        'es-parse',
        help='Parse logs stored in Elasticsearch indices using Grok and index results',
        description="Retrieves logs from source indices (either all groups or a single specified group), generates Grok patterns via LLM, parses logs, and indexes structured results into target indices."
    )

    # --- NEW Argument: Target Group ---
    es_parse_parser.add_argument(
        '-g', '--group',
        type=str,
        default=None, # Default is None, meaning parse all groups
        help='(Optional) Specify the name of a single group to parse. If omitted, all groups found in the group info index will be processed.'
    )

    es_parse_parser.add_argument(
        '-f', '--field',
        type=str,
        default='content',
        help='The field in the source documents containing the raw log line to parse (default: content).'
    )
    es_parse_parser.add_argument(
        '--copy-fields',
        type=str,
        nargs='*',
        help='(Optional) List of additional fields from the source document to copy to the target parsed document.'
    )
    es_parse_parser.add_argument(
        '-b', '--batch-size',
        type=int,
        default=500,
        help='Number of documents to process/index per batch (default: 5000).'
    )
    es_parse_parser.add_argument(
        '-s', '--sample-size',
        type=int,
        default=20,
        help='Number of log lines to sample for LLM Grok pattern generation (default: 20).'
    )

    # Threads Argument (Still relevant for all-groups parallel mode)
    default_threads = 1
    try: max_threads = multiprocessing.cpu_count(); max_help = f"Max suggested: {max_threads}."
    except NotImplementedError: max_threads = 1; max_help = "Cannot determine max CPUs."

    es_parse_parser.add_argument(
        '-t', '--threads', type=int, default=default_threads,
        help=f'Number of parallel processes when parsing ALL groups (ignored if --group is specified). Default: {default_threads}. {max_help}'
    )

    # Set the function to be called
    es_parse_parser.set_defaults(func=handle_es_parse)
