# cli.py
import argparse
import sys

try:
    from logllm.cli import container, collect
    from logllm.utils.logger import Logger # Optional: for logging CLI actions
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="LogLLM Command Line Interface")
    subparsers = parser.add_subparsers(dest='command', help='Available commands', required=True)

    # Register command groups
    container.register_container_parser(subparsers)
    collect.register_collect_parser(subparsers)

    # Add more command registrations here as needed
    # e.g., parser_module.register_parser(subparsers)

    args = parser.parse_args()

    # Execute the function associated with the chosen command
    if hasattr(args, 'func'):
        args.func(args)
    else:
        # This should not happen if subparsers are required=True and have func set
        parser.print_help()

if __name__ == "__main__":
    # Optional: Initialize logger for CLI
    # logger = Logger(name="LogLLM_CLI", log_file="cli.log")
    # logger.info("CLI started")
    main()
    # logger.info("CLI finished")
