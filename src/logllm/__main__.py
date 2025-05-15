# src/logllm/cli/__main__.py
import argparse
import sys

try:
    from .cli import es_parse  # Import the new DB parser command file
    from .cli import parse  # Keep original file parser
    from .cli import collect, container, normalize_ts, pm
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="LogLLM Command Line Interface - Manage Containers, Collect, Parse (File/ES), Manage Prompts"  # Updated description
    )
    # Add global --test/--json args if es_parse needs PromptsManager
    parser.add_argument(
        "--verbose", action="store_true", help="Enable global verbose output"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use prompts/test.json for pm/parse commands",
    )
    parser.add_argument(
        "-j",
        "--json",
        type=str,
        help="Specify a custom JSON file path for pm/parse commands",
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Available commands", required=True
    )

    # Register command groups
    container.register_container_parser(subparsers)
    collect.register_collect_parser(subparsers)
    parse.register_parse_parser(subparsers)  # File parser
    es_parse.register_es_parse_parser(subparsers)  # ES parser << NEW
    pm.register_pm_parser(subparsers)
    normalize_ts.register_normalize_ts_parser(subparsers)

    try:
        args = parser.parse_args()
        if hasattr(args, "func"):
            args.func(args)
        else:
            # Handle cases where subcommands might be missing if not required=True
            parser.print_help()

    except Exception as cli_error:
        print(f"\nCLI Error: {cli_error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
