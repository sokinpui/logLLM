# src/logllm/cli/parse.py
import argparse
import os
import sys
import multiprocessing  # Import to get cpu_count
from typing import Dict, List, Optional  # Added typing

# Use try-except for robustness if structure changes or run context varies
try:
    # Adjust relative paths if necessary based on your project structure
    # *** Import the Grok agent and state, GroupLogParserAgent should internally use Grok now ***
    from ..agents.parser_agent import (
        GroupLogParserAgent,
        SimpleGrokLogParserAgent,
        SimpleGrokLogParserState,
    )
    from ..utils.llm_model import GeminiModel  # Or your base LLMModel class
    from ..utils.database import ElasticsearchDatabase  # Needed for Group parser
    from ..utils.logger import Logger
    from ..config import config as cfg
except ImportError as e:
    print(f"Error importing necessary modules for CLI 'parse' command: {e}")
    print("Ensure you are running from the correct directory and PYTHONPATH is set.")
    sys.exit(1)

logger = Logger()


def handle_parse(args):
    """Handles the logic for the 'parse' command using Grok."""
    # show_drain_progress renamed for clarity, though effect is minimal on Grok
    show_agent_progress = args.show_progress
    num_threads = args.threads  # Get thread count

    # Validate thread count
    if num_threads < 1:
        logger.warning(
            f"Invalid thread count ({num_threads}) specified. Defaulting to 1."
        )
        print(f"Warning: Invalid thread count ({num_threads}), using 1 thread.")
        num_threads = 1

    # --- Initialize required components (Main thread instance) ---
    try:
        logger.info("Initializing LLM Model for Grok parsing (main thread instance)...")
        # Model initialized once here. Used for:
        # 1. Single file parsing (-f)
        # 2. Group pattern pre-determination or sequential parsing (-d)
        model = GeminiModel()
    except Exception as e:
        logger.error(f"Failed to initialize LLM Model: {e}", exc_info=True)
        print(f"Error: Could not initialize the LLM Model. {e}")
        return  # Cannot proceed without the model

    # --- Route based on provided arguments (-d or -f) ---
    if args.directory:
        # --- Directory Parsing Logic (Using GroupLogParserAgent with Grok worker) ---
        # Check if user incorrectly provided a pattern with directory parsing
        if args.grok_pattern:  # Check the renamed argument
            logger.warning(
                "--grok-pattern is ignored when using -d/--directory parsing."
            )
            print("Warning: --grok-pattern option is only applicable with -f/--file.")

        logger.info(
            f"Executing group Grok parse command for directory '{args.directory}'. Threads: {num_threads}"
        )
        print(
            f"Starting Grok parsing for all logs associated with collected groups using {num_threads} worker(s)..."
        )
        if show_agent_progress:
            # Note: Grok agent itself doesn't produce continuous progress like Drain
            print("(--show-progress enabled: Detailed per-file status will be shown)")
        else:
            print("(Progress bar will be shown for sequential runs)")

        try:
            # GroupLogParserAgent now uses SimpleGrokLogParserAgent internally via its worker
            agent = GroupLogParserAgent(model=model)
            # Pass thread count and show_progress flag to the agent's run method
            # show_progress mainly affects the sequential progress bar display now
            parsing_results = agent.run(
                num_threads=num_threads, show_progress=show_agent_progress
            )

            # --- Display Summary ---
            print("\n--- Grok Parsing Summary ---")
            successful_groups = 0
            total_csvs = 0
            failed_groups = []
            if not parsing_results:
                print(
                    "No parsing results returned. Check logs for errors fetching groups or during parsing."
                )
                return

            for group, csv_paths in parsing_results.items():
                if csv_paths and isinstance(csv_paths, list) and len(csv_paths) > 0:
                    print(
                        f"Group '{group}': {len(csv_paths)} CSVs generated successfully"
                    )
                    successful_groups += 1
                    total_csvs += len(csv_paths)
                else:
                    # Handle cases where parsing might have failed for all files in the group
                    print(
                        f"Group '{group}': No CSVs generated or parsing failed (check logs)"
                    )
                    failed_groups.append(group)

            print("\n--- Overall ---")
            print(f"Total Groups Processed: {len(parsing_results)}")
            print(f"Groups with at least one successful parse: {successful_groups}")
            print(f"Total CSV files generated: {total_csvs}")
            if failed_groups:
                print(f"Groups with no successful parses: {', '.join(failed_groups)}")
            print("Group Grok parsing finished. Check logs for details and warnings.")

        except Exception as e:
            logger.error(
                f"An error occurred during group Grok parsing: {e}", exc_info=True
            )
            print(f"\nAn error occurred during group Grok parsing: {e}")
            import traceback

            traceback.print_exc()

    elif args.file:
        # --- Single File Parsing Logic (Using SimpleGrokLogParserAgent) ---
        if num_threads > 1:
            logger.warning(
                f"-t/--threads set to {num_threads}, but single file parsing (-f) is always sequential. Ignoring thread count."
            )
            print("Warning: Thread count ignored for single file parsing.")

        file_path = args.file
        logger.info(f"Executing Grok parse command for single file: {file_path}")
        if not os.path.isfile(file_path):
            logger.error(f"File not found: {file_path}")
            print(f"Error: File not found: {file_path}")
            return

        # Get the Grok pattern from the argument (or None)
        grok_pattern = args.grok_pattern
        prep_message = (
            f"--- Preparing to Grok parse single file '{os.path.basename(file_path)}'"
        )
        if grok_pattern:
            logger.info(f"Using provided Grok pattern: {grok_pattern}")
            prep_message += " with provided pattern"
        else:
            logger.info(f"No Grok pattern provided, LLM will generate one.")
            prep_message += " (LLM will generate pattern)"
        prep_message += " ---"
        print(prep_message)
        # show_agent_progress doesn't control Grok's internal verbosity
        # but we acknowledge the flag was set
        if show_agent_progress:
            print("(--show-progress enabled)")

        try:
            # *** Use the SimpleGrokLogParserAgent and its State ***
            agent = SimpleGrokLogParserAgent(model=model)
            state: SimpleGrokLogParserState = {
                "log_file_path": file_path,
                "grok_pattern": grok_pattern,  # Pass user pattern or None
                "output_csv_path": "",
                "sample_logs": "",  # Populated by agent if needed
                "parsed_lines": 0,  # Populated by agent
                "skipped_lines": 0,  # Populated by agent
            }

            # Pass the show_progress flag (minimal effect on Grok agent itself)
            result_state = agent.run(state, show_progress=show_agent_progress)

            # --- Display Result ---
            print("\n--- Grok Parsing Result ---")
            output_csv = result_state.get("output_csv_path")
            parsed = result_state.get("parsed_lines", 0)
            skipped = result_state.get("skipped_lines", 0)
            # Get the pattern actually used (might have been generated)
            final_pattern = result_state.get("grok_pattern", "N/A")

            if output_csv:
                print(f"Status: SUCCESS")
                print(f"Output CSV: {output_csv}")
                print(f"Lines Parsed: {parsed}, Lines Skipped: {skipped}")
                if (
                    not args.grok_pattern and final_pattern != "N/A"
                ):  # Check if pattern was generated
                    print(f"Generated Grok pattern used: {final_pattern}")
                elif args.grok_pattern:  # Pattern was provided
                    print(f"Provided Grok pattern used: {final_pattern}")
            else:
                print(f"Status: FAILED")
                print(f"Lines Parsed: {parsed}, Lines Skipped: {skipped}")
                # Explain why it might have failed
                if final_pattern == "N/A":
                    print("Reason: Failed to generate or provide a valid Grok pattern.")
                elif skipped > 0 and parsed == 0:
                    print(
                        "Reason: The Grok pattern did not match any lines in the file."
                    )
                    print(f"Pattern used: {final_pattern}")
                elif parsed > 0:
                    print(
                        "Reason: Parsing started but may have encountered an error during processing or writing CSV."
                    )
                    print(f"Pattern used: {final_pattern}")
                else:  # Should ideally not happen if pattern was valid but no lines read
                    print("Reason: Unknown failure. Check logs.")
                    print(f"Pattern used: {final_pattern}")

                print("Check logs for specific errors or pattern mismatch warnings.")

        except Exception as e:
            logger.error(
                f"An error occurred during single file Grok parsing: {e}", exc_info=True
            )
            print(f"\nAn error occurred during single file Grok parsing: {e}")
            import traceback

            traceback.print_exc()

    else:
        # This case should not be reached if the mutually exclusive group is required
        logger.error(
            "Invalid state in handle_parse: Neither directory nor file specified."
        )
        print("Internal Error: Please specify either --directory or --file.")


def register_parse_parser(subparsers):
    """Registers the 'parse' command and its arguments for Grok parsing."""
    parse_parser = subparsers.add_parser(
        "parse",
        # Updated help message
        help="Parse log files using Grok patterns (requires collected logs for -d)",
        # Updated description
        description="Parses log files using Grok patterns. Use -d for group parsing (can be parallelized with -t), -f for single file. LLM can generate patterns if not provided.",
    )

    # --- Mutually Exclusive Group for Directory or File ---
    input_group = parse_parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "-d",
        "--directory",
        type=str,
        help="Path to the ORIGINAL log directory (triggers group parsing based on info in DB)",
    )
    input_group.add_argument(
        "-f", "--file", type=str, help="Path to a single log file to parse"
    )

    # --- Optional Grok Pattern (Only for Single File) ---
    parse_parser.add_argument(
        # Renamed from --log-format
        "--grok-pattern",
        type=str,
        # Updated help
        help="(Optional) Specify the Grok pattern string. Only applicable when using -f/--file. If omitted, LLM will attempt generation.",
    )

    # --- Show Progress Flag ---
    # Kept for consistency, though its effect on Grok parsing is mainly
    # controlling the sequential progress bar in GroupLogParserAgent.
    parse_parser.add_argument(
        "-v",
        "--show-progress",
        action="store_true",
        help="Show detailed per-file status updates instead of suppressing them (primarily affects sequential group parsing display).",
    )

    # --- Threads Argument ---
    default_threads = 1
    try:
        max_threads = multiprocessing.cpu_count()
        max_help = f"Max suggested: {max_threads}."
    except NotImplementedError:
        max_threads = 1  # Fallback
        max_help = "Cannot determine max CPUs."

    parse_parser.add_argument(
        "-t",
        "--threads",
        type=int,
        default=default_threads,
        help=f"Number of parallel processes for group parsing (-d). Default: {default_threads}. {max_help} Ignored for -f.",
    )

    # Set the function to be called when 'parse' is chosen
    parse_parser.set_defaults(func=handle_parse)
