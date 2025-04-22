# src/logllm/cli/pm.py
import argparse
import os
import json
from ..utils.prompts_manager import PromptsManager  # Import from the new location
from ..utils.logger import Logger  # Optional: if you want logging within handlers

logger = Logger()  # Optional


# --- Helper Function to Get Manager Instance ---
# This centralizes getting the correct JSON file path based on global args
def _get_prompts_manager(args):
    json_file = (
        args.json
        if args.json
        else "prompts/test.json"
        if args.test
        else "prompts/prompts.json"
    )
    # Ensure the directory exists for the manager to work correctly, especially for git init
    os.makedirs(os.path.dirname(json_file) or ".", exist_ok=True)
    return PromptsManager(json_file=json_file)


# --- Handler Functions for each pm subcommand ---


def handle_pm_scan(args):
    """Handles the 'pm scan' command."""
    prompts_manager = _get_prompts_manager(args)
    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a valid directory")
        logger.error(f"Scan directory not found: {args.directory}")
        return

    logger.info(
        f"Executing pm scan: dir={args.directory}, recursive={args.recursive}, hard={args.hard}"
    )
    if args.hard:
        if args.recursive:
            updated_keys = prompts_manager._hard_update_prompt_store_recursive(
                args.directory, commit_message=args.message
            )
        else:
            updated_keys = prompts_manager._hard_update_prompt_store(
                args.directory, commit_message=args.message
            )
    else:
        if args.recursive:
            updated_keys = prompts_manager._update_prompt_store_recursive(
                args.directory, commit_message=args.message
            )
        else:
            updated_keys = prompts_manager._update_prompt_store(
                args.directory, commit_message=args.message
            )

    if updated_keys:
        print(f"Updated keys in {prompts_manager.json_file} from {args.directory}:")
        for key in updated_keys:
            print(f"  - {key}")
    else:
        print(f"No new keys added from {args.directory}")

    if args.verbose_pm:  # Use a different name to avoid clash with global verbose
        print(f"\nCurrent {prompts_manager.json_file} content:")
        print(json.dumps(prompts_manager.prompts, indent=4))
    logger.info("pm scan finished.")


def handle_pm_list(args):
    """Handles the 'pm list' command."""
    prompts_manager = _get_prompts_manager(args)
    logger.info(f"Executing pm list: only_prompts={args.prompt}")
    prompts_manager.list_prompts(only_prompts=args.prompt)
    if args.verbose_pm:
        print(f"\nCurrent {prompts_manager.json_file} content:")
        print(json.dumps(prompts_manager.prompts, indent=4))
    logger.info("pm list finished.")


def handle_pm_add(args):
    """Handles the 'pm add' command."""
    prompts_manager = _get_prompts_manager(args)
    logger.info(f"Executing pm add: key={args.key}")
    if args.value is not None:
        prompt_value = args.value
    elif args.file is not None:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                prompt_value = f.read()
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found")
            logger.error(f"Prompt file not found: {args.file}")
            return
        except Exception as e:
            print(f"Error reading file '{args.file}': {e}")
            logger.error(f"Error reading prompt file '{args.file}': {e}", exc_info=True)
            return
    else:
        # This case should be prevented by argparse mutually exclusive group
        print("Internal Error: Neither value nor file provided for add.")
        logger.error("Invalid state in handle_pm_add: Neither value nor file.")
        return

    success = prompts_manager.add_prompt(
        args.key, prompt_value, commit_message=args.message
    )
    if success and args.verbose_pm:
        print(f"\nCurrent {prompts_manager.json_file} content:")
        print(json.dumps(prompts_manager.prompts, indent=4))
    logger.info(f"pm add finished for key '{args.key}'. Success: {success}")


def handle_pm_delete(args):
    """Handles the 'pm delete' command."""
    prompts_manager = _get_prompts_manager(args)
    logger.info(f"Executing pm delete for keys: {args.key}")
    deleted_keys = prompts_manager.delete_keys(args.key, commit_message=args.message)
    if deleted_keys:
        print(f"Deleted keys from {prompts_manager.json_file}:")
        for key in deleted_keys:
            print(f"  - {key}")
    else:
        print("No keys were deleted (none found or already absent).")

    if args.verbose_pm:
        print(f"\nCurrent {prompts_manager.json_file} content:")
        print(json.dumps(prompts_manager.prompts, indent=4))
    logger.info(f"pm delete finished. Deleted: {deleted_keys}")


def handle_pm_version(args):
    """Handles the 'pm version' command."""
    prompts_manager = _get_prompts_manager(args)
    logger.info(
        f"Executing pm version: key={args.key}, verbose={args.verbose_hist}, tail={args.tail}, free={args.free}"
    )
    prompts_manager.list_versions(
        key=args.key,
        verbose=args.verbose_hist,  # Use distinct name
        tail=args.tail,
        free=args.free,
    )
    logger.info("pm version finished.")


def handle_pm_revert(args):
    """Handles the 'pm revert' command."""
    prompts_manager = _get_prompts_manager(args)
    logger.info(
        f"Executing pm revert: commit={args.commit}, key={args.key}, verbose={args.verbose_rev}"
    )
    success = prompts_manager.revert_version(
        commit_hash=args.commit,
        key=args.key,
        commit_message=args.message,
        verbose=args.verbose_rev,  # Use distinct name
    )
    # Output is handled within revert_version, just log completion
    logger.info(f"pm revert finished. Success: {success}")
    if success and args.verbose_pm:
        print(f"\nCurrent {prompts_manager.json_file} content after revert:")
        print(json.dumps(prompts_manager.prompts, indent=4))


def handle_pm_diff(args):
    """Handles the 'pm diff' command."""
    prompts_manager = _get_prompts_manager(args)
    logger.info(
        f"Executing pm diff: c1={args.commit1}, c2={args.commit2}, key={args.key}, verbose={args.verbose_diff}"
    )
    prompts_manager.show_diff(
        commit1=args.commit1,
        commit2=args.commit2,
        key=args.key,
        verbose=args.verbose_diff,  # Use distinct name
    )
    logger.info("pm diff finished.")


# --- Registration Function ---
def register_pm_parser(subparsers):
    """Registers the 'pm' command and its subcommands."""
    pm_parser = subparsers.add_parser(
        "pm",
        help="Manage prompts in JSON file (prompts.json/test.json)",
        description="Provides tools to scan code, list, add, delete, and version control prompts stored in a JSON file.",
    )
    # Add arguments specific to 'pm' actions if needed (but global --json/--test/--verbose are handled in __main__)
    pm_parser.add_argument(
        "--verbose-pm",
        action="store_true",
        help="Print the entire prompt store content after pm actions (scan, list, add, delete, revert).",
    )

    pm_subparsers = pm_parser.add_subparsers(
        dest="pm_action", help="Prompts Manager action", required=True
    )

    # --- Replicate argparse setup from original prompts_manager.py main() ---

    # 'scan' action
    scan_parser = pm_subparsers.add_parser(
        "scan", help="Scan a directory to update the prompt store"
    )
    scan_parser.add_argument(
        "-d", "--directory", type=str, required=True, help="Directory to scan"
    )
    scan_parser.add_argument(
        "-r", "--recursive", action="store_true", help="Recursively scan subdirectories"
    )
    scan_parser.add_argument(
        "--hard",
        action="store_true",
        help="Perform a hard update (removes keys not found)",
    )
    # scan_parser.add_argument("--verbose", action="store_true", help="Print the entire prompt store content") # Handled by --verbose-pm
    scan_parser.add_argument(
        "-m",
        "--message",
        type=str,
        nargs="?",
        default=None,
        const="",
        help="Custom Git commit message; omit value for editor, no arg for default",
    )
    scan_parser.set_defaults(func=handle_pm_scan)  # Link to handler

    # 'list' action
    list_parser = pm_subparsers.add_parser("list", help="List keys in the prompt store")
    list_parser.add_argument(
        "-p", "--prompt", action="store_true", help="Only show keys with prompt strings"
    )
    # list_parser.add_argument("--verbose", action="store_true", help="Print the entire prompt store content") # Handled by --verbose-pm
    list_parser.set_defaults(func=handle_pm_list)

    # 'add' action
    add_parser = pm_subparsers.add_parser(
        "add", help="Add or update a prompt for an existing key"
    )
    add_parser.add_argument(
        "-k",
        "--key",
        type=str,
        required=True,
        help="The key to update (e.g., 'module.class.func')",
    )
    add_value_group = add_parser.add_mutually_exclusive_group(required=True)
    add_value_group.add_argument(
        "-v", "--value", type=str, help="The string value to assign"
    )
    add_value_group.add_argument(
        "-f", "--file", type=str, help="File path to read the prompt string from"
    )
    # add_parser.add_argument("--verbose", action="store_true", help="Print the entire prompt store content") # Handled by --verbose-pm
    add_parser.add_argument(
        "-m",
        "--message",
        type=str,
        nargs="?",
        default=None,
        const="",
        help="Custom Git commit message; omit value for editor, no arg for default",
    )
    add_parser.set_defaults(func=handle_pm_add)

    # 'delete' action
    delete_parser = pm_subparsers.add_parser(
        "rm", help="Delete keys from the prompt store"
    )
    delete_parser.add_argument(
        "-k", "--key", type=str, nargs="+", required=True, help="Keys to delete"
    )
    # delete_parser.add_argument("--verbose", action="store_true", help="Print the entire prompt store content") # Handled by --verbose-pm
    delete_parser.add_argument(
        "-m",
        "--message",
        type=str,
        nargs="?",
        default=None,
        const="",
        help="Custom Git commit message; omit value for editor, no arg for default",
    )
    delete_parser.set_defaults(func=handle_pm_delete)

    # 'version' action
    version_parser = pm_subparsers.add_parser(
        "version", help="List version history of prompts"
    )
    version_parser.add_argument(
        "-k", "--key", type=str, help="Key to show version history for"
    )
    version_parser.add_argument(
        "--verbose-hist",
        type=int,
        nargs="?",
        const=50,
        default=50,  # Renamed
        help="Print first n chars of prompt (default 50, -1 for full prompt)",
    )
    version_parser.add_argument(
        "-t",
        "--tail",
        type=int,
        nargs="?",
        const=-1,
        default=-1,
        help="Show last n commits (default all, -1 for all commits)",
    )
    version_parser.add_argument(
        "--free",
        action="store_true",
        help="Use free-form output instead of fixed-width boxed table",
    )
    version_parser.set_defaults(func=handle_pm_version)

    # 'revert' action
    revert_parser = pm_subparsers.add_parser(
        "revert", help="Revert to a previous version"
    )
    revert_parser.add_argument(
        "-c", "--commit", type=str, required=True, help="Commit hash to revert to"
    )
    revert_parser.add_argument(
        "-k", "--key", type=str, help="Key to revert; if omitted, reverts entire file"
    )
    revert_parser.add_argument(
        "--verbose-rev",
        type=int,
        nargs="?",
        const=50,
        default=50,  # Renamed
        help="Print first n chars of prompt after revert (default 50, -1 for full)",
    )
    # revert_parser.add_argument("--verbose", action="store_true", ...) # Use --verbose-pm instead
    revert_parser.add_argument(
        "-m",
        "--message",
        type=str,
        nargs="?",
        default=None,
        const="",
        help="Custom Git commit message; omit value for editor, no arg for default",
    )
    revert_parser.set_defaults(func=handle_pm_revert)

    # 'diff' action
    diff_parser = pm_subparsers.add_parser(
        "diff", help="Show diff between two commits for the prompt store"
    )
    diff_parser.add_argument(
        "-c1", "--commit1", type=str, required=True, help="First commit hash to compare"
    )
    diff_parser.add_argument(
        "-c2",
        "--commit2",
        type=str,
        required=True,
        help="Second commit hash to compare",
    )
    diff_parser.add_argument(
        "-k", "--key", type=str, help="Key to filter diff for (optional)"
    )
    diff_parser.add_argument(
        "--verbose-diff",
        type=int,
        nargs="?",
        const=50,
        default=50,  # Renamed
        help="Print first n chars of prompt/JSON in diff (default 50, -1 for full)",
    )
    diff_parser.set_defaults(func=handle_pm_diff)
