## File: `prompts_manager.py`

### Class: `PromptsManager`
- **Purpose**: Manages a JSON-based prompt store (default: `prompts/prompts.json`, or custom via `--json`/`--test`) for storing and retrieving prompts associated with Python code structures (directories, modules, classes, and functions). It supports scanning directories to populate the store, deleting keys, listing keys, adding/updating prompts, retrieving prompts with placeholder substitution, and version control via Git for tracking changes to the prompt store. Designed as a reusable utility module.
- **Location**: Recommended to place in `utils/` (e.g., `project_root/utils/prompts_manager.py`).
- **Dependencies**: Requires Python standard libraries (`os`, `ast`, `json`, `argparse`, `re`, `inspect`, `subprocess`, `datetime`) and `typing` for type hints. Requires `git` installed and accessible in the system PATH for version control features.

#### Key Methods:
- **`__init__(self, json_file: str = "prompts/prompts.json")`**
  - **Description**: Initializes the `PromptsManager` with a specified JSON file path. Loads existing prompts if the file exists and ensures the containing directory is a Git repository for version control.
  - **Parameters**:
    - `json_file` (str): Path to the JSON file (default: `"prompts/prompts.json"`, overridden by `--json` or `--test` in CLI).
  - **Returns**: None
  - **Usage**: Creates a `PromptsManager` instance for prompt management and version control.
  - **Example**:
    ```python
    from utils.prompts_manager import PromptsManager
    pm = PromptsManager("custom/prompts.json")  # Custom file
    ```

- **`_load_prompts(self)`**
  - **Description**: Loads the existing prompts from the JSON file into memory. Returns an empty dictionary if the file doesn’t exist.
  - **Parameters**: None
  - **Returns**: dict - The loaded prompts.
  - **Usage**: Internal method called during initialization to populate `self.prompts`.
  - **Example**: Not called directly; used by `__init__`.
  - **Where to Use**: N/A (internal).

- **`_save_prompts(self)`**
  - **Description**: Saves the current `self.prompts` dictionary to the JSON file, creating the containing directory if it doesn’t exist, and commits the change to a Git repository in that directory.
  - **Parameters**: None
  - **Returns**: None
  - **Usage**: Internal method called after updates, deletions, additions, or reverts to persist changes and record them in Git.
  - **Example**: Not called directly; used by other methods.
  - **Where to Use**: N/A (internal).

- **`_ensure_git_repo(self)`**
  - **Description**: Ensures the directory containing the JSON file (e.g., `prompts/`) is a Git repository. Initializes it with an initial commit if it doesn’t exist.
  - **Parameters**: None
  - **Returns**: None
  - **Usage**: Internal method called during initialization to enable version control.
  - **Example**: Not called directly; used by `__init__`.
  - **Where to Use**: N/A (internal).

- **`_update_prompt_store(self, dir: str)`**
  - **Description**: Scans a top-level directory for Python files, extracts class and function structures using AST, and updates `prompts.json` with new entries (e.g., `"no prompts"`). Preserves existing entries and commits changes to Git.
  - **Parameters**:
    - `dir` (str): Directory path to scan (e.g., `"tests/"`).
  - **Returns**: List[str] - Keys added or modified.
  - **Usage**: Use to populate or refresh the prompt store non-recursively.
  - **Example**:
    ```python
    pm = PromptsManager()
    updated = pm._update_prompt_store("tests/")
    print(updated)  # e.g., ["tests.t.TextClass.run"]
    ```
  - **Where to Use**: Internal use within CLI or custom scripts; prefer `scan` action for general use.

- **`_update_prompt_store_recursive(self, dir: str, current_dict: Dict[str, Any] = None, base_path: str = "")`**
  - **Description**: Recursively scans a directory and subdirectories for Python files, updating `prompts.json` with proper nesting and committing changes to Git.
  - **Parameters**:
    - `dir` (str): Directory path to scan.
    - `current_dict` (Dict[str, Any], optional): Current dictionary level (internal).
    - `base_path` (str, optional): Base path for key construction (internal).
  - **Returns**: List[str] - Keys added or modified.
  - **Usage**: Use for recursive updates across a directory tree.
  - **Example**:
    ```python
    pm = PromptsManager()
    updated = pm._update_prompt_store_recursive("tests/")
    print(updated)  # e.g., ["tests.subdir.nested.NestedClass.run"]
    ```
  - **Where to Use**: Internal use within CLI or custom scripts; prefer `scan -r` for general use.

- **`_hard_update_prompt_store(self, dir: str)`**
  - **Description**: Performs a hard update on a top-level directory, rebuilding its subtree in `prompts.json`, removing non-existent entries, preserving existing prompt values, and committing changes to Git.
  - **Parameters**:
    - `dir` (str): Directory path to scan.
  - **Returns**: List[str] - Keys in the updated subtree.
  - **Usage**: Use to synchronize `prompts.json` with a single directory.
  - **Example**:
    ```python
    pm = PromptsManager()
    updated = pm._hard_update_prompt_store("tests/")
    print(updated)  # e.g., ["tests.t.TextClass.run"]
    ```
  - **Where to Use**: Internal use within CLI or custom scripts; prefer `scan --hard` for general use.

- **`_hard_update_prompt_store_recursive(self, dir: str, current_dict: Dict[str, Any] = None, base_path: str = "")`**
  - **Description**: Recursively performs a hard update across a directory tree, preserving prompt values, removing non-existent entries, and committing changes to Git.
  - **Parameters**:
    - `dir` (str): Directory path to scan.
    - `current_dict` (Dict[str, Any], optional): Current dictionary level (internal).
    - `base_path` (str, optional): Base path for key construction (internal).
  - **Returns**: List[str] - Keys in the updated subtree.
  - **Usage**: Use for recursive synchronization.
  - **Example**:
    ```python
    pm = PromptsManager()
    updated = pm._hard_update_prompt_store_recursive("tests/")
    print(updated)  # e.g., ["tests.subdir.nested.NestedClass.run"]
    ```
  - **Where to Use**: Internal use within CLI or custom scripts; prefer `scan -r --hard` for general use.

- **`list_prompts(self, only_prompts: bool = False)`**
  - **Description**: Lists all keys in `prompts.json` or only those with string prompt values, returning them as a list of lists. Prints keys in a readable format.
  - **Parameters**:
    - `only_prompts` (bool): If `True`, only list keys with string values (prompts); if `False`, list all keys (default: `False`).
  - **Returns**: List[List[str]] - Keys as lists (e.g., `[["tests", "t", "TextClass", "run"]]`) .
  - **Usage**: Use programmatically to inspect or process the prompt store’s structure, or via CLI with `list`.
  - **Example**:
    ```python
    pm = PromptsManager()
    all_keys = pm.list_prompts()  # All keys
    prompt_keys = pm.list_prompts(only_prompts=True)  # Only prompt keys
    print(all_keys)  # e.g., [["tests", "t", "TextClass", "run"]]
    ```
  - **Where to Use**: Ideal for debugging, auditing, or integrating with other code needing prompt metadata.

- **`add_prompt(self, key: str, value: str)`**
  - **Description**: Adds or updates a prompt for an existing key in `prompts.json` if the key has a string value (i.e., is a prompt field), committing the change to Git.
  - **Parameters**:
    - `key` (str): Dot-notation key (e.g., `"tests.t.TextClass.run"`).
    - `value` (str): New prompt value (e.g., `"Hello, {name}"`).
  - **Returns**: bool - `True` if successful, `False` if the key doesn’t exist or isn’t a prompt field.
  - **Usage**: Use programmatically to set or update prompts dynamically, or via CLI with `add`.
  - **Example**:
    ```python
    pm = PromptsManager()
    success = pm.add_prompt("tests.t.TextClass.run", "Hello, {name}")
    if success:
        print("Prompt updated")
    ```
  - **Where to Use**: Useful in scripts, agents, or workflows to customize prompts programmatically.

- **`delete_keys(self, keys: list[str])`**
  - **Description**: Deletes specified keys from `prompts.json` using dot notation, commits the change to Git, and returns the list of successfully deleted keys.
  - **Parameters**:
    - `keys` (list[str]): List of keys to delete (e.g., `["tests.t.TextClass.run"]`).
  - **Returns**: List[str] - Keys that were deleted.
  - **Usage**: Use to remove outdated or unwanted entries programmatically or via CLI with `delete`.
  - **Example**:
    ```python
    pm = PromptsManager()
    deleted = pm.delete_keys(["tests.t.TextClass.run"])
    print(deleted)  # ["tests.t.TextClass.run"]
    ```
  - **Where to Use**: Use in maintenance scripts or application logic to clean up `prompts.json`.

- **`get_prompt(self, metadata: str = None, **variables: str) -> str`**
  - **Description**: Retrieves a prompt from `prompts.json` using either a provided metadata string or runtime-resolved metadata. Substitutes placeholders with provided variables.
  - **Parameters**:
    - `metadata` (str, optional): Dot-separated path to the prompt (e.g., `"tests.t.TextClass.run"`). If `None`, resolved at runtime.
    - `**variables` (str): Keyword arguments for placeholder substitution (e.g., `name="Alice"`).
  - **Returns**: str - The prompt with placeholders replaced.
  - **Raises**:
    - `KeyError`: If the prompt isn’t found.
    - `ValueError`: If placeholders and variables mismatch.
    - `RuntimeError`: If runtime metadata resolution fails.
  - **Usage**: Call within a class method for dynamic prompt retrieval or with explicit metadata for manual control.
  - **Example**:
    ```python
    class TextClass:
        def __init__(self):
            self.pm = PromptsManager()

        def run(self):
            return self.pm.get_prompt(name="Bob")  # Resolves to "tests.t.TextClass.run"

    pm = PromptsManager()
    prompt = pm.get_prompt("tests.t.TextClass.run", name="Alice")
    print(prompt)  # "Hello, Alice"
    ```
  - **Where to Use**: Core method for integrating prompts into application logic, especially in agent-based systems.

- **`list_versions(self, key: str = None, verbose: int = 50, tail: int = -1, free: bool = False) -> List[Dict[str, str]]`**
  - **Description**: Lists the Git commit history for the JSON file or a specific key, sorted by timestamp (descending). Displays commit hash, message, and optionally the prompt (truncated or full based on `verbose`). In `non-free` mode, the output is a boxed table with fixed-width columns, where commit messages longer than the default width are truncated with `...` for alignment. In `free` mode, the output is a simple list with full commit messages and prompts. No extra newlines are added between commits in either mode, ensuring a compact display.
  - **Parameters**:
    - `key` (str, optional): Dot-notation key to filter history (e.g., `"tests.t.TextClass.run"`). If `None`, lists all commits for the file.
    - `verbose` (int): Number of characters to display for prompts (default: 50; -1 for full prompt).
    - `tail` (int): Number of recent commits to display (default: -1, meaning all commits).
    - `free` (bool): If `True`, uses free-form output without boxed formatting; if `False`, uses a boxed table (default: `False`).
  - **Returns**: List[Dict[str, str]] - History entries with keys `"commit"`, `"timestamp"`, `"message"`, and `"prompt"` (if applicable).
  - **Usage**: Use to inspect the version history of the prompt store or a specific prompt, either programmatically or via CLI with `version`. The output is a continuous list of commits with no extra newlines between entries, making it compact and readable.
  - **Example**:
    ```python
    pm = PromptsManager()
    history = pm.list_versions("tests.t.TextClass.run", verbose=-1, tail=5, free=False)
    for entry in history:
        print(f"{entry['timestamp']} | {entry['commit'][:8]} | {entry['prompt']}")
    ```
  - **Where to Use**: Useful for auditing changes, debugging, or integrating version history into workflows.
  - **Output Example (Non-Free Mode)**:
    ```
    Version history for 'tests.t.TextClass.run' in prompts/test.json:
    ---------------------------------------------------------------------------------------------------------
    | b36461a2 | asdf                                       | Prompt: no prompts
    | 6438581b | Update test.json at Mar 19, 2025 11:18 PM  | Prompt: {msg}
    | f5ee7beb | asdfasdfas                                 | Prompt: no prompts
    | 64246262 | Update test.json at Mar 19, 2025 11:15 PM  | Prompt: {msg}
    | e9497cb8 | Update test.json at Mar 19, 2025 11:05 PM  | Prompt: no prompts
    ---------------------------------------------------------------------------------------------------------
    ```
  - **Output Example (Free Mode with Multi-Line Prompt)**:
    ```
    Version history for 'tests.t.TextClass.run' in prompts/test.json:
    | 7929627b | Update test.json at Mar 19, 2025 03:27 PM | Prompt: # Project logLLM

    **logLLM** is a multi-agent syst
    | bda32aca | Update test.json at Mar 19, 2025 03:27 PM | Prompt: {name}
    | 30b0f7f7 | Update test.json at Mar 19, 2025 03:10 PM | Prompt: no prompts
    ```

- **`revert_version(self, commit_hash: str, key: str = None, verbose: int = 50)`**
  - **Description**: Reverts the entire JSON file or a specific key to a previous commit state, identified by its Git commit hash, and commits the revert action.
  - **Parameters**:
    - `commit_hash` (str): Git commit hash to revert to (short or full).
    - `key` (str, optional): Dot-notation key to revert (e.g., `"tests.t.TextClass.run"`). If `None`, reverts the entire file.
    - `verbose` (int): Number of characters to display for the reverted prompt (default: 50; -1 for full prompt).
  - **Returns**: bool - `True` if successful, `False` if the revert fails (e.g., key not found).
  - **Usage**: Use to rollback changes programmatically or via CLI with `revert`.
  - **Example**:
    ```python
    pm = PromptsManager()
    success = pm.revert_version("abc12345", "tests.t.TextClass.run", verbose=-1)
    if success:
        print("Reverted successfully")
    ```
  - **Where to Use**: Ideal for restoring previous prompt states in development or production scenarios.

- **`show_diff(self, commit1: str, commit2: str, key: str = None, verbose: int = 50)`**
  - **Description**: Displays a readable diff between two Git commits for the entire JSON file or a specific key, showing `commit1: <prompt>` and `commit2: <prompt>` for key-specific diffs.
  - **Parameters**:
    - `commit1` (str): First commit hash to compare.
    - `commit2` (str): Second commit hash to compare.
    - `key` (str, optional): Dot-notation key to filter diff (e.g., `"tests.t.TextClass.run"`).
    - `verbose` (int): Number of characters to display for prompts (default: 50; -1 for full).
  - **Returns**: None (prints the diff directly).
  - **Usage**: Use to compare prompt changes between commits programmatically or via CLI with `diff`.
  - **Example**:
    ```python
    pm = PromptsManager()
    pm.show_diff("abc12345", "def67890", "tests.t.TextClass.run", verbose=-1)
    # Output:
    # Diff for key 'tests.t.TextClass.run' between abc12345 and def67890 in prompts/prompts.json:
    # abc12345: Old prompt
    # def67890: New prompt with {data}
    ```
  - **Where to Use**: Useful for reviewing prompt evolution or debugging version changes.

---

### Programmatic API Usage
The `PromptsManager` class is designed for broad use across your project. Public methods like `list_prompts`, `add_prompt`, `delete_keys`, `get_prompt`, `list_versions`, and `revert_version` are recommended for integration into other codebases.

#### Initializing and Managing
```python
from utils.prompts_manager import PromptsManager

pm = PromptsManager()

# List prompts
keys = pm.list_prompts()
print("All keys:", keys)

# Add a prompt
pm.add_prompt("tests.t.TextClass.run", "Hello, {name}")

# List versions
history = pm.list_versions("tests.t.TextClass.run", verbose=-1)
print("Version history:", history)

# Revert a key
pm.revert_version("abc12345", "tests.t.TextClass.run")

# Delete a key
pm.delete_keys(["tests.t.TextClass.run"])

# Get a prompt
prompt = pm.get_prompt("tests.t.TextClass.run", name="Alice")
print("Prompt:", prompt)
```

#### Example Integration with Version Control
```python
class LogAgent:
    def __init__(self):
        self.pm = PromptsManager()

    def process_log(self, log_data):
        # Check version history
        history = self.pm.list_versions("agents.log_agent.process_log")
        print("Prompt history:", history)

        # Add a custom prompt if needed
        self.pm.add_prompt("agents.log_agent.process_log", "Analyze {data}")

        # Use the prompt
        return self.pm.get_prompt("agents.log_agent.process_log", data=log_data)

agent = LogAgent()
print(agent.process_log("error log"))  # "Analyze error log"
```

---

### Command-Line Interface (CLI)
Run from the project root where `prompts/` is a subdirectory (unless overridden by `--json`). The prompt store is version-controlled using Git in the directory containing the JSON file (e.g., `prompts/`).

#### Usage
```bash
python utils/prompts_manager.py [ACTION] [OPTIONS] [-j PATH] [--test]
```

#### Actions and Options
- **`scan`**:
  - **Description**: Scans a directory to update the prompt store and commits changes to Git.
  - **Flags**:
    - `-d, --directory <DIR>` (required): Directory to scan.
    - `-r, --recursive`: Recursively scan subdirectories.
    - `--hard`: Perform a hard update, removing non-existent entries.
    - `--verbose`: Print the full prompt store content.
  - **Example**:
    ```bash
    python utils/prompts_manager.py scan -d tests/ -r -j custom/prompts.json
    ```

- **`list`**:
  - **Description**: Lists all keys or only prompt keys.
  - **Flags**:
    - `-p, --prompt`: Restrict to keys with string prompts.
    - `--verbose`: Print the full prompt store content.
  - **Example**:
    ```bash
    python utils/prompts_manager.py list --prompt -j custom/prompts.json
    ```

- **`add`**:
  - **Description**: Adds or updates a prompt for an existing key and commits the change to Git.
  - **Flags**:
    - `-k, --key <KEY>` (required): Key in dot notation.
    - `-v, --value <VALUE>` (required): New prompt string.
    - `--verbose`: Print the full prompt store content.
  - **Example**:
    ```bash
    python utils/prompts_manager.py add -k tests.t.TextClass.run -v "Hello, {name}" -j custom/prompts.json
    ```

- **`delete`**:
  - **Description**: Deletes specified keys from the prompt store and commits the change to Git.
  - **Flags**:
    - `-k, --key <KEY1> <KEY2> ...` (required): Keys to delete.
    - `--verbose`: Print the full prompt store content.
  - **Example**:
    ```bash
    python utils/prompts_manager.py delete -k tests.t.TextClass.run -j custom/prompts.json
    ```

- **`version`**:
  - **Description**: Lists the Git commit history for the prompt store or a specific key, sorted by timestamp (descending). Displays a compact list with no extra newlines between commits. In default (non-free) mode, uses a boxed table with fixed-width columns, truncating long commit messages with `...` for alignment. In free mode, displays a simple list with full commit messages and prompts.
  - **Flags**:
    - `-k, --key <KEY>`: Key to show version history for (optional).
    - `--verbose [N]`: Print the first N characters of the prompt (default: 50; -1 for full prompt).
    - `-t, --tail <N>`: Show the last N commits (default: -1, meaning all commits).
    - `--free`: Use free-form output instead of the default boxed table format.
  - **Example**:
    ```bash
    python utils/prompts_manager.py version -k tests.t.TextClass.run --verbose -1 -t 5 -j custom/prompts.json
    ```
    **Output**:
    ```
    Version history for 'tests.t.TextClass.run' in custom/prompts.json:
    ---------------------------------------------------------------------------------------------------------
    | b36461a2 | asdf                                       | Prompt: no prompts
    | 6438581b | Update test.json at Mar 19, 2025 11:18 PM  | Prompt: {msg}
    | f5ee7beb | asdfasdfas                                 | Prompt: no prompts
    | 64246262 | Update test.json at Mar 19, 2025 11:15 PM  | Prompt: {msg}
    | e9497cb8 | Update test.json at Mar 19, 2025 11:05 PM  | Prompt: no prompts
    ---------------------------------------------------------------------------------------------------------
    ```
  - **Example (Free Mode)**:
    ```bash
    python utils/prompts_manager.py version -k tests.t.TextClass.run --verbose -1 -t 5 --free -j custom/prompts.json
    ```
    **Output**:
    ```
    Version history for 'tests.t.TextClass.run' in custom/prompts.json:
    | b36461a2 | asdf | Prompt: no prompts
    | 6438581b | Update test.json at Mar 19, 2025 11:18 PM | Prompt: {msg}
    | f5ee7beb | asdfasdfas | Prompt: no prompts
    | 64246262 | Update test.json at Mar 19, 2025 11:15 PM | Prompt: {msg}
    | e9497cb8 | Update test.json at Mar 19, 2025 11:05 PM | Prompt: no prompts
    ```

- **`revert`**:
  - **Description**: Reverts the entire prompt store or a specific key to a previous commit and commits the revert action to Git.
  - **Flags**:
    - `-c, --commit <HASH>` (required): Commit hash to revert to.
    - `-k, --key <KEY>`: Key to revert (optional; if omitted, reverts entire file).
    - `--verbose [N]`: Print the first N characters of the reverted prompt (default: 50; -1 for full prompt; non-default also prints full JSON content).
  - **Example**:
    ```bash
    python utils/prompts_manager.py revert -c abc12345 -k tests.t.TextClass.run --verbose -1 -j custom/prompts.json
    ```
    **Output**:
    ```
    Reverted 'tests.t.TextClass.run' to version from commit abc12345: 'Hello, this is a long prompt fully displayed'
    Current custom/prompts.json content:
    {
        "tests": {
            "t": {
                "TextClass": {
                    "run": "Hello, this is a long prompt fully displayed"
                }
            }
        }
    }
    ```

- **`diff`**:
  - **Description**: Shows a readable diff between two commits for the prompt store or a specific key, formatted as `commit1: <prompt>` and `commit2: <prompt>`.
  - **Flags**:
    - `-c1, --commit1 <HASH>` (required): First commit hash to compare.
    - `-c2, --commit2 <HASH>` (required): Second commit hash to compare.
    - `-k, --key <KEY>`: Key to filter diff (optional).
    - `--verbose [N]`: Print the first N characters of prompts (default: 50; -1 for full).
  - **Example**:
    ```bash
    python utils/prompts_manager.py diff -c1 abc12345 -c2 def67890 -k tests.t.TextClass.run --verbose -1 -j custom/prompts.json
    ```
    **Output**:
    ```
    Diff for key 'tests.t.TextClass.run' between abc12345 and def67890 in custom/prompts.json:
    abc12345: Old prompt
    def67890: New prompt with {data}
    ```

- **`--test`**:
  - **Description**: Uses `prompts/test.json` instead of the default `prompts/prompts.json` (overridden by `--json`).
  - **Example**:
    ```bash
    python utils/prompts_manager.py scan -d tests/ --test
    ```

- **`-j, --json <PATH>`**:
  - **Description**: Specifies a custom JSON file path for the prompt store, overriding `--test` and the default `prompts/prompts.json`. The directory containing the file (including subdirectories) must exist and will be initialized as a Git repository if not already one.
  - **Example**:
    ```bash
    python utils/prompts_manager.py scan -d tests/ -j custom/prompts.json --verbose
    ```
    **Output**:
    ```
    Updated keys in custom/prompts.json from tests/:
      - tests.t.TextClass.run
    Current custom/prompts.json content:
    {
        "tests": {
            "t": {
                "TextClass": {
                    "run": "no prompts"
                }
            }
        }
    }
    ```

- **No Arguments**:
  - **Description**: Displays the help message.
  - **Example**:
    ```bash
    python utils/prompts_manager.py -j custom/prompts.json
    ```

#### Directory Context
- **Run From**: Project root (e.g., `project_root/`), unless `--json` specifies a different base path.
- **Target Directories**: Use relative paths (e.g., `tests/`).
- **Version Control**: The directory containing the JSON file (e.g., `prompts/`) is managed as a separate Git repository. To avoid conflicts with the parent project’s Git repository, consider adding the directory to `.gitignore` (e.g., `prompts/`) or converting it to a Git submodule.

---

### Notes
- **Version Control**: The prompt store is versioned using Git in the directory containing the JSON file (e.g., `prompts/`), initialized automatically by `_ensure_git_repo`. Changes are committed with timestamps for tracking.
- **Submodule Consideration**: If integrating into a larger Git-managed project, the prompt store’s directory (e.g., `prompts/`) can be added as a Git submodule for better portability (e.g., `git submodule add <url> prompts`).

---
