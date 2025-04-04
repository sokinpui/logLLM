# src/logllm/cli/__main__.py
import argparse
import sys

# Adjust relative paths based on where __main__.py lives relative to cli modules
try:
    # Assuming __main__.py is one level above container.py, collect.py, parse.py
    from .cli import container
    from .cli import collect
    from .cli import parse
    from .cli import pm # <--- Import the new pm module
except ImportError as e:
    print(f"Import Error: {e}")
    # Add more robust import handling if necessary (see previous examples)
    print("Please ensure the package is installed correctly or run using 'python -m logllm.cli'")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="LogLLM Command Line Interface - Manage Containers, Collect Logs, Parse Logs, Manage Prompts" # Updated description
    )

    # --- Add Global Arguments needed by PromptsManager ---
    parser.add_argument("--verbose", action="store_true", help="Enable global verbose output (may affect multiple commands)")
    parser.add_argument("--test", action="store_true", help="Use prompts/test.json for pm commands")
    parser.add_argument("-j", "--json", type=str, help="Specify a custom JSON file path for pm commands")
    # --- End Global Arguments ---

    subparsers = parser.add_subparsers(
        dest='command',
        help='Available commands',
        required=True
    )

    # Register command groups
    container.register_container_parser(subparsers)
    collect.register_collect_parser(subparsers)
    parse.register_parse_parser(subparsers)
    pm.register_pm_parser(subparsers) # <--- Register the pm parser

    # Add more command registrations here as needed

    try:
        args = parser.parse_args()

        # Execute the function associated with the chosen command
        # Note: The func attribute is now set by the deepest subparser invoked
        if hasattr(args, 'func'):
            args.func(args)
        else:
            # This might happen if a top-level command like 'pm' is called without a subcommand
            # Find the relevant parser to print help for
            if args.command == 'pm':
                 # Find the 'pm' parser object to print its specific help
                 # This is a bit hacky as argparse doesn't directly expose subparsers easily after parsing
                 # A common workaround is to re-parse with '-h' if no func is found for a known group
                 # Or, structure registration to keep parser objects accessible.
                 # For simplicity here, just print main help.
                 print("Command 'pm' requires a subcommand (e.g., scan, list, add).")
                 parser.print_help() # Or print pm_parser help if you can access it
            else:
                 parser.print_help() # Should not happen if subparsers are required=True

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
