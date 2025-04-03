# src/logllm/cli/parse.py
import argparse
import os
import sys
from typing import Dict, List # Added typing

# Use try-except for robustness if structure changes or run context varies
try:
    from ..agents.parser_agent import GroupLogParserAgent, SimpleDrainLogParserAgent, SimpleDrainLogParserState
    from ..utils.llm_model import GeminiModel # Or your base LLMModel class if you have a factory
    from ..utils.database import ElasticsearchDatabase # Needed for Group parser
    from ..utils.logger import Logger
    from ..config import config as cfg # If needed for model name etc.
except ImportError:
    print("Error importing necessary modules for CLI 'parse' command.")
    # Provide more context if possible, e.g., which module failed
    print("Ensure you are running from the correct directory and PYTHONPATH is set.")
    sys.exit(1)

logger = Logger()

def handle_parse(args):
    """Handles the logic for the 'parse' command."""

    # --- Initialize required components ---
    try:
        logger.info("Initializing LLM Model for parsing...")
        # Assuming GeminiModel is the one used by your agents
        # You might want to fetch the model name from config: cfg.GEMINI_LLM_MODEL
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

        logger.info(f"Executing parse command for directory '{args.directory}' (using collected group info).")
        print(f"Starting parsing for all logs associated with collected groups...")

        try:
            # GroupLogParserAgent needs the model
            agent = GroupLogParserAgent(model=model)
            # The agent fetches groups from Elasticsearch internally
            parsing_results = agent.run()

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

    elif args.file:
        # --- Single File Parsing Logic ---
        file_path = args.file
        logger.info(f"Executing parse command for single file: {file_path}")
        if not os.path.isfile(file_path):
            logger.error(f"File not found: {file_path}")
            print(f"Error: File not found: {file_path}")
            return

        log_format = args.log_format # This will be None if not provided
        if log_format:
            logger.info(f"Using provided log format: {log_format}")
            print(f"Attempting to parse '{os.path.basename(file_path)}' with provided format...")
        else:
            logger.info(f"No log format provided, LLM will generate one for: {os.path.basename(file_path)}")
            print(f"Attempting to parse '{os.path.basename(file_path)}' (LLM will generate format)...")

        try:
            # SimpleDrainLogParserAgent needs the model
            agent = SimpleDrainLogParserAgent(model=model)

            # Prepare the initial state
            state: SimpleDrainLogParserState = {
                "log_file_path": file_path,
                "log_format": log_format, # Pass user format or None
                "output_csv_path": "",    # Will be populated by the agent
                "sample_logs": ""         # Will be populated by the agent if needed
            }

            result_state = agent.run(state)

            # --- Display Result ---
            if result_state.get("output_csv_path"):
                logger.info(f"Successfully parsed file. Output: {result_state['output_csv_path']}")
                print(f"\nSuccessfully parsed '{os.path.basename(file_path)}'.")
                print(f"Output CSV: {result_state['output_csv_path']}")
                if not log_format and result_state.get("log_format"):
                     print(f"Generated log format used: {result_state['log_format']}")
            else:
                logger.error(f"Failed to parse file: {file_path}")
                print(f"\nFailed to parse '{os.path.basename(file_path)}'. Check logs for details.")
                if not log_format and result_state.get("log_format"):
                     # Even if parsing failed, show the format if it was generated
                     print(f"Generated log format (parsing failed): {result_state['log_format']}")


        except Exception as e:
            logger.error(f"An error occurred during single file parsing: {e}", exc_info=True)
            print(f"\nAn error occurred during single file parsing: {e}")

    else:
        # This case should not be reached if the mutually exclusive group is required
        logger.error("Invalid state in handle_parse: Neither directory nor file specified.")
        print("Internal Error: Please specify either --directory or --file.")


def register_parse_parser(subparsers):
    """Registers the 'parse' command and its arguments."""
    parse_parser = subparsers.add_parser(
        'parse',
        help='Parse log files using Drain (requires collected logs for -d)',
        description="Parses log files. Use -d to parse all logs based on previously collected group information stored in Elasticsearch. Use -f to parse a single specified log file."
    )

    # --- Mutually Exclusive Group for Directory or File ---
    input_group = parse_parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '-d', '--directory',
        type=str,
        help='Path to the ORIGINAL log directory (triggers parsing for all associated files found by the previous \'collect\' run based on group info in DB)'
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

    # Set the function to be called when 'parse' is chosen
    parse_parser.set_defaults(func=handle_parse)
