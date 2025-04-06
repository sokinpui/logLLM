# src/logllm/cli/es_parse.py

import argparse
import sys
import multiprocessing

try:
    from ..agents.es_parser_agent import AllGroupsParserAgent, AllGroupsParserState # Added State import
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
    batch_size = args.batch_size # Get batch size from args
    sample_size = args.sample_size # Get sample size from args

    if num_threads < 1:
        logger.warning(f"Invalid thread count ({num_threads}) specified. Defaulting to 1.")
        num_threads = 1
    if batch_size < 1:
        logger.warning(f"Invalid batch size ({batch_size}) specified. Defaulting to 5000.")
        batch_size = 5000 # Use default if invalid
    if sample_size < 1:
        logger.warning(f"Invalid sample size ({sample_size}) specified. Defaulting to 20.")
        sample_size = 20 # Use default if invalid


    logger.info(f"Executing Elasticsearch parse command. Threads: {num_threads}, Batch Size: {batch_size}, Sample Size: {sample_size}")
    print(f"Starting Elasticsearch log parsing. Workers: {num_threads}, Batch Size: {batch_size}, Sample Size: {sample_size}")

    try:
        # --- Initialize Dependencies ---
        logger.info("Initializing components for Elasticsearch parsing...")
        db = ElasticsearchDatabase()
        if db.instance is None:
             logger.error("Elasticsearch connection failed. Cannot proceed.")
             print("Error: Could not connect to Elasticsearch.")
             return

        model = GeminiModel()
        json_file = getattr(args, 'json', None) or ("prompts/test.json" if getattr(args, 'test', False) else "prompts/prompts.json")
        prompts_manager = PromptsManager(json_file=json_file)

        # --- Initialize Top-Level Agent ---
        agent = AllGroupsParserAgent(model=model, db=db, prompts_manager=prompts_manager)

        # --- Prepare Initial State (No changes needed here for sizes) ---
        initial_state: AllGroupsParserState = { # Specify type hint
            "group_info_index": cfg.INDEX_GROUP_INFOS,
            "field_to_parse": args.field,
            "fields_to_copy": args.copy_fields,
            "group_results": {},
            "status": "pending"
        }

        # --- Run the Agent, passing the sizes ---
        final_state = agent.run(
            initial_state=initial_state,
            num_threads=num_threads,
            batch_size=batch_size, # Pass batch size
            sample_size=sample_size # Pass sample size
        )

        # --- Display Summary (No changes needed here) ---
        print("\n--- Elasticsearch Parsing Summary ---")
        # ... (rest of summary display logic remains the same) ...
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
                 processed = parse_result.get("processed_count", 0) if parse_result else 0
                 indexed = parse_result.get("indexed_count", 0) if parse_result else 0
                 errors = parse_result.get("error_count", 0) if parse_result else 0

                 print(f"\nGroup '{group_name}':")
                 print(f"  Status: {status}")
                 print(f"  Grok Pattern Used: {pattern}")
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


        logger.info("Elasticsearch parsing finished.")

    except Exception as e:
        logger.error(f"An error occurred during Elasticsearch parsing orchestration: {e}", exc_info=True)
        print(f"\nAn critical error occurred: {e}")
        import traceback
        traceback.print_exc()


def register_es_parse_parser(subparsers):
    """Registers the 'es-parse' command and its arguments."""
    es_parse_parser = subparsers.add_parser(
        'es-parse',
        help='Parse logs stored in Elasticsearch indices using Grok and index results',
        description="Retrieves logs from source indices, generates Grok patterns via LLM, parses logs, and indexes structured results into target indices."
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

    # --- NEW Argument: Batch Size ---
    es_parse_parser.add_argument(
        '-b', '--batch-size',
        type=int,
        default=5000, # Default value
        help='Number of documents to process/index per batch during Elasticsearch scroll/bulk operations (default: 5000).'
    )

    # --- NEW Argument: Sample Size ---
    es_parse_parser.add_argument(
        '-s', '--sample-size',
        type=int,
        default=20, # Default value
        help='Number of log lines to sample from each group for LLM Grok pattern generation (default: 20).'
    )

    # --- Threads Argument (Remains the same) ---
    default_threads = 1
    try:
        max_threads = multiprocessing.cpu_count()
        max_help = f"Max suggested: {max_threads}."
    except NotImplementedError:
        max_threads = 1
        max_help = "Cannot determine max CPUs."

    es_parse_parser.add_argument(
        '-t', '--threads', type=int, default=default_threads,
        help=f'Number of parallel processes for parsing GROUPS. Default: {default_threads}. {max_help}'
    )

    # Set the function to be called
    es_parse_parser.set_defaults(func=handle_es_parse)
