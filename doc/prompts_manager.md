# Detailed Documentation for `src/logllm/utils/prompts_manager.py` and the `pm` CLI Command

# Prompts Management

The `logLLM` project includes a robust system for managing Large Language Model (LLM) prompts. This involves:

1.  **A `PromptsManager` utility class** (`src/logllm/utils/prompts_manager.py`):

    - This class provides the core logic for storing prompts in a structured JSON file (e.g., `prompts/prompts.json`).
    - It integrates with Git for version control of the prompt file, allowing tracking, comparison, and reversion of changes.
    - It offers a programmatic API for agents and other parts of the system to retrieve and use prompts dynamically, including placeholder substitution.
    - **Detailed documentation for the `PromptsManager` class itself can be found in [./utils/prompts_manager_utility.md](./utils/prompts_manager_utility.md).**

2.  **A `pm` CLI command** (`python -m src.logllm pm ...`):
    - This command-line interface allows users to interact with the `PromptsManager` to scan codebases for prompt locations, list existing prompts, add/update prompts, delete prompts, and manage prompt versions (view history, revert, diff).
    - **Detailed documentation for the `pm` CLI command and its subcommands can be found in [./cli/pm.md](./cli/pm.md).**

This dual approach provides both programmatic flexibility for internal use and a user-friendly CLI for managing the prompt lifecycle.

## Overview

The `PromptsManager` class, located in `src/logllm/utils/prompts_manager.py`, provides a robust system for managing Large Language Model (LLM) prompts associated with the project's codebase. It stores prompts in a structured JSON file (defaulting to `prompts/prompts.json`) and leverages Git for version control, allowing tracking, comparison, and reversion of prompt changes.

Interaction with the `PromptsManager` is primarily done through the `pm` subcommand of the main `logLLM` CLI (`python -m src.logllm pm ...`).

## Key Features

- **Centralized Storage**: Keeps prompts organized in a single JSON file, mapping them to code structures (directory/module/class/function).
- **Code Scanning**: Automatically scans Python code directories (`pm scan`) to discover potential prompt locations (functions within classes) and initializes them in the JSON file.
- **Git Version Control**: Automatically initializes a Git repository in the prompts directory (e.g., `prompts/`) and commits every change made via the `pm` command, enabling history tracking (`pm version`), comparison (`pm diff`), and rollback (`pm revert`).
- **Programmatic Access**: The `PromptsManager` class offers methods (`get_prompt`, `add_prompt`, `list_prompts`, etc.) for use within agents or other scripts.
- **Placeholder Substitution**: The `get_prompt` method supports f-string-like placeholders (e.g., `{variable_name}`) for dynamic prompt generation at runtime.
- **Flexible Configuration**: The prompt file location can be customized using the global `--json <PATH>` or `--test` CLI flags.

## `PromptsManager` Class (`src/logllm/utils/prompts_manager.py`)

This class provides the core logic for interacting with the prompts JSON file and its Git history.

### Initialization

- **`__init__(self, json_file: str = "prompts/prompts.json")`**
  - Creates an instance linked to a specific JSON file.
  - Loads existing prompts from the file.
  - Ensures the directory containing the JSON file is a Git repository (initializes if necessary).

### Programmatic API (Key Methods)

_(Refer to [utils.md](./utils.md#file-srclogllmutilsprompts_managerpy) for a detailed API breakdown of the PromptsManager class itself.)_

- **`get_prompt(metadata: str = None, **variables) -> str`\*\*: Retrieves a prompt, performs variable substitution. Can resolve metadata automatically if called from within a class method.
- **`add_prompt(key: str, value: str, commit_message: str = None) -> bool`**: Adds or updates a specific prompt string for a key. Saves and commits.
- **`list_prompts(only_prompts: bool = False) -> List[List[str]]`**: Lists keys in the store.
- **`delete_keys(keys: List[str], commit_message: str = None) -> List[str]`**: Removes keys from the store. Saves and commits.
- **`list_versions(key: str = None, verbose: int = 50, tail: int = -1, free: bool = False) -> List[Dict]`**: Shows Git history for the file or a specific key.
- **`revert_version(commit_hash: str, key: str = None, commit_message: str = None, verbose: int = 50) -> bool`**: Reverts the file or a key to a specific commit. Saves and commits.
- **`show_diff(commit1: str, commit2: str, key: str = None, verbose: int = 50)`**: Shows differences between two commits.
- **Internal Scan Methods** (`_update_prompt_store`, `_hard_update_prompt_store`, etc.): Used by the `pm scan` command.

## CLI Usage (`pm` Subcommand)

The `pm` command provides a command-line interface to the `PromptsManager` functionality.

**Base Command:**

```bash
python -m src.logllm [GLOBAL_OPTIONS] pm [ACTION] [ACTION_OPTIONS]
```

**Global Options (Used _before_ `pm`):**

- `--verbose`: Enable detailed application logging.
- `--test`: Use `prompts/test.json` as the prompt file.
- `-j, --json <PATH>`: Use a custom `<PATH>` for the prompt file (overrides `--test` and default `prompts/prompts.json`). The directory for `<PATH>` must exist.

**`pm` Command Specific Options:**

- `--verbose-pm`: Print the entire prompt store content after actions that modify it (scan, add, rm, revert).

---

### Actions (`pm [ACTION]`)

- **`scan`**: Scans code directories to update the prompt store structure.

  - **Usage**: `python -m src.logllm pm scan -d <DIR> [OPTIONS]`
  - **Options**:
    - `-d, --directory <DIR>` (Required): Directory path to scan (e.g., `src/logllm/agents`).
    - `-r, --recursive`: Scan subdirectories recursively.
    - `--hard`: Hard update: removes keys from the scanned directory's subtree in the JSON if they no longer exist in the code. Preserves existing prompt values.
    - `-m, --message [MSG]`: Custom Git commit message. If flag is present but no `MSG` is given, opens the default Git editor. If flag is omitted, uses a default timestamped message.
  - **Example**:

    ```bash
    # Recursive scan, custom commit message
    python -m src.logllm pm scan -d src/logllm/agents -r -m "Update agent prompts structure"

    # Hard update, default commit message
    python -m src.logllm -j custom/my_prompts.json pm scan -d src/logllm/utils --hard
    ```

- **`list`**: Lists keys in the prompt store.

  - **Usage**: `python -m src.logllm pm list [OPTIONS]`
  - **Options**:
    - `-p, --prompt`: Show only keys that currently hold prompt strings (leaf nodes).
  - **Example**:
    ```bash
    python -m src.logllm --test pm list --prompt
    ```

- **`add`**: Adds or updates a prompt string for a specific key.

  - **Usage**: `python -m src.logllm pm add -k <KEY> (-v <VALUE> | -f <FILE>) [OPTIONS]`
  - **Options**:
    - `-k, --key <KEY>` (Required): The dot-separated key (e.g., `src.logllm.agents.parser_agent.SimpleGrokLogParserAgent._generate_grok_pattern`).
    - `-v, --value <VALUE>` (Required, Mutually Exclusive with `-f`): The prompt string value.
    - `-f, --file <FILE>` (Required, Mutually Exclusive with `-v`): File path to read the prompt string from.
    - `-m, --message [MSG]`: Custom Git commit message (see `scan` for details).
  - **Example**:

    ```bash
    # Add prompt directly
    python -m src.logllm pm add -k key.path.to.func -v "Analyze: {data}" -m "Add analysis prompt"

    # Add prompt from file
    python -m src.logllm pm add -k key.path.to.func -f ./prompt_text.txt
    ```

- **`rm`**: Removes keys from the prompt store.

  - **Usage**: `python -m src.logllm pm rm -k <KEY1> [<KEY2>...] [OPTIONS]`
  - **Options**:
    - `-k, --key <KEY...>` (Required): One or more dot-separated keys to delete.
    - `-m, --message [MSG]`: Custom Git commit message (see `scan` for details).
  - **Example**:
    ```bash
    python -m src.logllm pm rm -k key.path.to.delete another.key.path
    ```

- **`version`**: Lists the Git commit history for the prompt file or a specific key.

  - **Usage**: `python -m src.logllm pm version [OPTIONS]`
  - **Options**:
    - `-k, --key <KEY>`: Filter history for a specific key.
    - `--verbose-hist [N]` (Optional, default: 50): Max characters of the prompt to show (use -1 for full). Renamed from `--verbose`.
    - `-t, --tail [N]` (Optional, default: -1): Show only the last N commits (-1 for all).
    - `--free`: Use free-form output instead of a boxed table.
  - **Example**:
    ```bash
    python -m src.logllm pm version -k key.path.to.func --verbose-hist -1 --tail 10
    ```

- **`revert`**: Reverts the prompt file or a specific key to a previous commit state.

  - **Usage**: `python -m src.logllm pm revert -c <HASH> [OPTIONS]`
  - **Options**:
    - `-c, --commit <HASH>` (Required): The Git commit hash (short or full) to revert to.
    - `-k, --key <KEY>`: Revert only this specific key (optional; reverts entire file if omitted).
    - `--verbose-rev [N]` (Optional, default: 50): Max characters of the reverted prompt to show (use -1 for full). Renamed from `--verbose`.
    - `-m, --message [MSG]`: Custom Git commit message for the revert action (see `scan` for details).
  - **Example**:
    ```bash
    python -m src.logllm pm revert -c a1b2c3d -k key.path.to.func -m "Revert prompt for key.path.to.func"
    ```

- **`diff`**: Shows differences in prompts between two commits.
  - **Usage**: `python -m src.logllm pm diff -c1 <HASH1> -c2 <HASH2> [OPTIONS]`
  - **Options**:
    - `-c1, --commit1 <HASH1>` (Required): First commit hash.
    - `-c2, --commit2 <HASH2>` (Required): Second commit hash.
    - `-k, --key <KEY>`: Show diff only for this specific key (optional).
    - `--verbose-diff [N]` (Optional, default: 50): Max characters of prompt/JSON content to show in diff (use -1 for full). Renamed from `--verbose`.
  - **Example**:
    ```bash
    python -m src.logllm pm diff -c1 HEAD~1 -c2 HEAD -k key.path.to.func --verbose-diff -1
    ```

---

### Version Control Integration

- The directory specified by `--json` (or the default `prompts/`) is treated as a Git repository.
- `PromptsManager` automatically handles `git add` and `git commit` after modifications made via the `pm` command or relevant class methods.
- **Recommendation**: Add the prompts directory (e.g., `prompts/`, or your custom path) to the main project's `.gitignore` file to prevent nested Git repositories unless you intend to manage it as a submodule.
