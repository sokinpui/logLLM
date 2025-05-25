# src/logllm/cli/__main__.py
import argparse
import sys

try:
    from .cli import (
        analyze_errors,
        collect,
        container,
        normalize_ts,
        pm,
        static_grok_parse,
    )
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="LogLLM Command Line Interface - Manage Containers, Collect, Parse (Static Grok), Manage Prompts"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable global verbose output"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use prompts/test.json for pm commands",
    )
    parser.add_argument(
        "-j",
        "--json",
        type=str,
        help="Specify a custom JSON file path for pm commands",
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Available commands", required=True
    )

    # Register command groups
    container.register_container_parser(subparsers)
    collect.register_collect_parser(subparsers)
    static_grok_parse.register_static_grok_parse_parser(subparsers)
    pm.register_pm_parser(subparsers)
    normalize_ts.register_normalize_ts_parser(subparsers)
    analyze_errors.register_analyze_errors_parser(subparsers)

    try:
        args = parser.parse_args()
        if hasattr(args, "func"):
            args.func(args)
        else:
            parser.print_help()

    except Exception as cli_error:
        print(f"\nCLI Error: {cli_error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
