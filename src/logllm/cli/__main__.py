# src/logllm/cli/__main__.py
import argparse
import sys
import os

# Adjust relative paths based on where __main__.py lives relative to cli modules
try:
    # Assuming __main__.py is one level above container.py, collect.py, parse.py
    from . import container
    from . import collect
    from . import parse # Import the new module
    from ..utils.logger import Logger # Optional: for logging CLI actions
except ImportError as e:
    print(f"Import Error: {e}")
    # Add more robust import handling if necessary (see previous examples)
    print("Please ensure the package is installed correctly or run using 'python -m logllm.cli'")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="LogLLM Command Line Interface - Manage Containers, Collect Logs, Parse Logs"
    )
    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
        required=True
    )

    # Register command groups
    container.register_container_parser(subparsers)
    collect.register_collect_parser(subparsers)
    parse.register_parse_parser(subparsers) # Register the parser commands

    # Add more command registrations here as needed

    try:
        args = parser.parse_args()

        # Execute the function associated with the chosen command
        if hasattr(args, 'func'):
            args.func(args)
        else:
            # This should not happen if subparsers are required=True and have func set
            parser.print_help()
    except Exception as cli_error:
         # Catch potential errors during argument parsing or handler execution
         print(f"\nCLI Error: {cli_error}")
         # Consider adding logger.error(...) here as well
         # Optionally print traceback for debugging:
         # import traceback
         # traceback.print_exc()
         sys.exit(1)


if __name__ == "__main__":
    # Optional: Initialize logger for CLI
    # logger = Logger(name="LogLLM_CLI", log_file="cli.log") # Use your enhanced logger
    # logger.info("CLI started")
    main()
    # logger.info("CLI finished")
