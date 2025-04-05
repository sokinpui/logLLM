# src/logllm/cli/parse.py
import argparse
import os
import sys
import multiprocessing # Import to get cpu_count
from typing import Dict, List, Optional # Added typing

# Use try-except for robustness if structure changes or run context varies
try:
    # Adjust relative paths if necessary based on your project structure
    from ..agents.parser_agent import GroupLogParserAgent, SimpleDrainLogParserAgent, SimpleDrainLogParserState
    from ..utils.llm_model import GeminiModel # Or your base LLMModel class if you have a factory
    from ..utils.database import ElasticsearchDatabase # Needed for Group parser (though agent uses it)
    from ..utils.logger import Logger
    from ..config import config as cfg # If needed for model name etc.
except ImportError as e:
    print(f"Error importing necessary modules for CLI 'parse' command: {e}")
    # Provide more context if possible, e.g., which module failed
    print("Ensure you are running from the correct directory and PYTHONPATH is set.")
    # Add fallback import logic if needed (see previous examples)
    sys.exit(1)

logger = Logger()

def handle_parse(args):
    """Handles the logic for the 'parse' command."""
    show_drain_progress = args.show_progress # Get the flag value
    num_threads = args.threads # Get thread count

    # Validate thread count
    if num_threads < 1:
        logger.warning(f"Invalid thread count ({num_threads}) specified. Defaulting to 1.")
        print(f"Warning: Invalid thread count ({num_threads}), using 1 thread.")
        num_threads = 1

    # --- Initialize required components (Main thread instance) ---
    try:
        logger.info("Initializing LLM Model for parsing (main thread instance)...")
        # Model initialized once here. It's used directly for:
        # 1. Single file parsing (-f)
        # 2. Group parsing (-d) when threads=1
        # 3. Determining initial group formats before parallel workers start
        # Parallel workers (-d with threads > 1) will initialize their own instances.
        model = GeminiModel()
    except Exception as e:
        logger.error(f"Failed to initialize LLM Model: {e}", exc_info=True)
        print(f"Error: Could not initialize the LLM Model. {e}")
        return # Cannot proceed without the model

    # --- Route based on provided arguments (-d or -f) ---
    if args.directory:
        # --- Directory Parsing Logic ---
        if args.log_format:
            logger.warning("--log-format is ignored when using -d/--directory parsing.")
            print("Warning: --log-format option is only applicable with -f/--file.")

        logger.info(f"Executing group parse command for directory '{args.directory}'. Threads: {num_threads}")
        print(f"Starting parsing for all logs associated with collected groups using {num_threads} worker(s)...")
        if show_drain_progress:
            print("(--show-progress enabled: Drain output will be visible)")

        try:
            # GroupLogParserAgent needs the model instance mainly for threads=1 case
            # or for determining group formats before starting workers.
            agent = GroupLogParserAgent(model=model)
            # Pass thread count and show_progress flag to the agent's run method
            parsing_results = agent.run(num_threads=num_threads, show_progress=show_drain_progress)

            # --- Display Summary ---
            print("\n--- Parsing Summary ---")
            successful_groups = 0
            total_csvs = 0
            failed_groups = []
            if not parsing_results:
                 print("No parsing results returned. Check logs for errors fetching groups or during parsing.")
                 return
            for group, csv_paths in parsing_results.items():
                if csv_paths:
                    print(f"Group '{group}': {len(csv_paths)} CSVs generated")
                    successful_groups += 1
                    total_csvs += len(csv_paths)
                else:
                    print(f"Group '{group}': No CSVs generated (check logs for errors)")
                    failed_groups.append(group)
            print("\n--- Overall ---")
            print(f"Total Groups Processed: {len(parsing_results)}")
            print(f"Groups with at least one successful parse: {successful_groups}")
            print(f"Total CSV files generated: {total_csvs}")
            if failed_groups:
                 print(f"Groups with no successful parses: {', '.join(failed_groups)}")
            print("Group parsing finished. Check logs for details.")

        except Exception as e:
            logger.error(f"An error occurred during group parsing: {e}", exc_info=True)
            print(f"\nAn error occurred during group parsing: {e}")
            # Optionally print traceback for debugging
            # import traceback
            # traceback.print_exc()

    elif args.file:
        # --- Single File Parsing Logic ---
        if num_threads > 1:
            # Inform the user that threading is ignored for single file
            logger.warning(f"-t/--threads set to {num_threads}, but single file parsing (-f) is always sequential. Ignoring thread count.")
            print("Warning: Thread count ignored for single file parsing.")

        file_path = args.file
        logger.info(f"Executing parse command for single file: {file_path}")
        if not os.path.isfile(file_path):
            logger.error(f"File not found: {file_path}")
            print(f"Error: File not found: {file_path}")
            return

        log_format = args.log_format
        prep_message = f"--- Preparing to parse single file '{os.path.basename(file_path)}'"
        if log_format:
            logger.info(f"Using provided log format: {log_format}")
            prep_message += " with provided format"
        else:
            logger.info(f"No log format provided, LLM will generate one.")
            prep_message += " (LLM will generate format)"
        prep_message += " ---"
        print(prep_message)
        if show_drain_progress:
            print("(--show-progress enabled: Drain output will be visible)")

        try:
            # Use the model instance initialized earlier for single file parsing
            agent = SimpleDrainLogParserAgent(model=model)
            state: SimpleDrainLogParserState = {
                "log_file_path": file_path,
                "log_format": log_format, # Pass user format or None
                "output_csv_path": "",    # Will be populated by the agent
                "sample_logs": ""         # Will be populated by the agent if needed
            }

            # Pass the show_progress flag to the agent's run method
            result_state = agent.run(state, show_progress=show_drain_progress)

            # --- Display Result ---
            print("\n--- Parsing Result ---") # Add marker after potential Drain output
            if result_state.get("output_csv_path"):
                print(f"Status: SUCCESS")
                print(f"Output CSV: {result_state['output_csv_path']}")
                if not log_format and result_state.get("log_format"):
                     print(f"Generated log format used: {result_state['log_format']}")
            else:
                print(f"Status: FAILED")
                if not log_format and result_state.get("log_format"):
                     print(f"Generated log format (parsing failed): {result_state['log_format']}")
                print("Check logs or scroll up for Drain error messages.")


        except Exception as e:
            logger.error(f"An error occurred during single file parsing: {e}", exc_info=True)
            print(f"\nAn error occurred during single file parsing: {e}")
            # Optionally print traceback for debugging
            # import traceback
            # traceback.print_exc()

    else:
        # This case should not be reached if the mutually exclusive group is required
        logger.error("Invalid state in handle_parse: Neither directory nor file specified.")
        print("Internal Error: Please specify either --directory or --file.")


def register_parse_parser(subparsers):
    """Registers the 'parse' command and its arguments."""
    parse_parser = subparsers.add_parser(
        'parse',
        help='Parse log files using Drain (requires collected logs for -d)',
        description="Parses log files. Use -d for group parsing (can be parallelized with -t), -f for single file."
    )

    # --- Mutually Exclusive Group for Directory or File ---
    input_group = parse_parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '-d', '--directory',
        type=str,
        help='Path to the ORIGINAL log directory (triggers group parsing based on info in DB)'
    )
    input_group.add_argument(
        '-f', '--file',
        type=str,
        help='Path to a single log file to parse'
    )

    # --- Optional Log Format (Only for Single File) ---
    parse_parser.add_argument(
        '--log-format',
        type=str,
        help='(Optional) Specify Drain log format string. Only applicable when using -f/--file.'
    )

    # --- Show Progress Flag ---
    parse_parser.add_argument(
        '--show',
        action='store_true', # Sets args.show_progress to True if flag is present
        help='Show Drain internal parsing progress/output instead of suppressing it.'
    )

    # --- Threads Argument ---
    default_threads = 1
    try:
        # Use cpu_count if available, otherwise default
        max_threads = multiprocessing.cpu_count()
        max_help = f"Max suggested: {max_threads}."
    except NotImplementedError:
        max_threads = 1 # Fallback if cpu_count is not implemented
        max_help = "Cannot determine max CPUs."

    parse_parser.add_argument(
        '-t', '--threads', type=int, default=default_threads,
        help=f'Number of parallel processes for group parsing (-d). Default: {default_threads}. {max_help} Ignored for -f.'
    )


    # Set the function to be called when 'parse' is chosen
    parse_parser.set_defaults(func=handle_parse)
