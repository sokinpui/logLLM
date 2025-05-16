# Prompts Manager Utility (`prompts_manager.py`)

## File: `src/logllm/utils/prompts_manager.py`

### Overview

The `PromptsManager` class provides a robust system for managing Large Language Model (LLM) prompts associated with the project's codebase. It stores prompts in a structured JSON file (defaulting to `prompts/prompts.json`) and leverages Git for version control, allowing tracking, comparison, and reversion of prompt changes.

For details on the Command Line Interface (`pm` command) that uses this class, see [../../cli/pm.md](../../cli/pm.md).

### Key Features of the Class

- **Centralized Storage**: Keeps prompts organized in a single JSON file, mapping them to code structures (directory/module/class/function).
- **Git Version Control**: Automatically initializes a Git repository in the prompts directory (e.g., `prompts/`) and commits every change made via relevant class methods, enabling history tracking, comparison, and rollback.
- **Programmatic Access**: Offers methods for use within agents or other scripts.
- **Placeholder Substitution**: The `get_prompt` method supports f-string-like placeholders (e.g., `{variable_name}`) for dynamic prompt generation at runtime.
- **Flexible Configuration**: The prompt file location can be customized during instantiation.

### `PromptsManager` Class

This class provides the core logic for interacting with the prompts JSON file and its Git history.

#### Initialization

- **`__init__(self, json_file: str = "prompts/prompts.json")`**
  - Creates an instance linked to a specific JSON file.
  - Loads existing prompts from the file.
  - Ensures the directory containing the JSON file is a Git repository (initializes if necessary using `_ensure_git_repo`).

#### Core Programmatic API

- **`_load_prompts() -> dict`**:
  - Internal method to load prompts from `self.json_file`. Returns an empty dictionary if the file doesn't exist.
- **`_save_prompts(commit_message: str = None)`**:
  - Internal method to save the current `self.prompts` dictionary to `self.json_file` and commit the changes to Git.
  - Handles default commit messages (timestamped), custom messages, or opening an editor if `commit_message == ""`.
- **`get_prompt(metadata: str = None, **variables) -> str`\*\*:
  - Retrieves a prompt string based on `metadata` (a dot-separated key like `module.class.function`).
  - If `metadata` is `None`, it dynamically resolves the key based on the caller's context (module, class, function name).
  - Performs f-string-like substitution using `**variables`.
  - Raises `KeyError` if the prompt is not found, or `ValueError` if variables are missing/extra.
- **`add_prompt(key: str, value: str, commit_message: str = None) -> bool`**:
  - Adds or updates a prompt string for the given `key`.
  - Saves the prompts and commits the change.
  - Returns `True` on success, `False` if the key path is invalid.
- **`delete_keys(keys: List[str], commit_message: str = None) -> List[str]`**:
  - Removes one or more `keys` from the prompt store.
  - Saves and commits.
  - Returns a list of keys that were actually deleted.
- **`list_prompts(only_prompts: bool = False) -> List[List[str]]`**:
  - Prints a list of all keys in the prompt store.
  - If `only_prompts` is `True`, it lists only keys that directly hold prompt strings (leaf nodes).
  - Returns the list of key paths (as lists of strings).
- **`list_versions(key: str = None, verbose: int = 50, tail: int = -1, free: bool = False) -> List[Dict]`**:
  - Lists the Git commit history for `self.json_file`.
  - If `key` is provided, filters history to show only commits affecting that specific prompt key.
  - `verbose` controls how much of the prompt text is shown (e.g., `50` chars, `-1` for full).
  - `tail` limits the number of commits shown.
  - `free` enables a less structured output format.
  - Returns a list of history entry dictionaries.
- **`revert_version(commit_hash: str, key: str = None, commit_message: str = None, verbose: int = 50) -> bool`**:
  - Reverts `self.json_file` (or just a specific `key` within it) to its state at the given `commit_hash`.
  - Saves and commits the reverted state.
  - Returns `True` on success.
- **`show_diff(commit1: str, commit2: str, key: str = None, verbose: int = 50)`**:
  - Shows the differences in prompts between two Git commits (`commit1` and `commit2`).
  - Can be filtered by `key`.
  - `verbose` controls the amount of differing text shown.

#### Internal Scan-Related Methods (Used by `pm scan` CLI)

- **`_update_prompt_store(dir: str, commit_message: str = None) -> list[str]`**: Scans the top-level `dir` for Python files and classes/functions, updating `self.prompts` with new keys (soft update).
- **`_update_prompt_store_recursive(dir: str, commit_message: str = None, current_dict: Dict = None, base_path: str = "") -> list[str]`**: Same as above, but scans recursively.
- **`_hard_update_prompt_store(dir: str, commit_message: str = None) -> list[str]`**: Hard update for top-level `dir` (removes keys from JSON if not in code, preserves existing values).
- **`_hard_update_prompt_store_recursive(dir: str, commit_message: str = None, current_dict: Dict = None, base_path: str = "") -> list[str]`**: Recursive hard update.
- **`_get_nested_value(d: Dict, keys: List[str]) -> Any`**: Helper to retrieve a value from a nested dictionary.
- **`_set_nested_value(d: Dict, keys: List[str], value: str) -> bool`**: Helper to set a value in a nested dictionary.
- **`_ensure_git_repo()`**: Ensures the prompt directory is a Git repository, initializing it if necessary.
