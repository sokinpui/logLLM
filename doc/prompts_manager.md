## File: `prompts_manager.py`

### Class: `PromptsManager`
- **Purpose**: Manages a JSON-based prompt store (`prompts.json`) for storing and retrieving prompts associated with Python code structures (directories, modules, classes, and functions). It supports scanning directories to populate the store, deleting keys, listing keys, adding/updating prompts, and retrieving prompts with placeholder substitution. Designed as a utility that can be imported and used across various parts of a project.
- **Location**: Recommended to place this file in a `utils/` directory within your project (e.g., `project_root/utils/prompts_manager.py`), as it serves as a reusable utility module.
- **Dependencies**: Requires Python standard libraries (`os`, `ast`, `json`, `argparse`, `re`, `inspect`) and `typing` for type hints.

#### Key Methods:
- **`__init__(self, json_file: str = "prompts/prompts.json")`**
  - **Description**: Initializes the `PromptsManager` with a specified JSON file path where prompts are stored. Loads existing prompts if the file exists.
  - **Parameters**:
    - `json_file` (str): Path to the JSON file (default: `"prompts/prompts.json"`).
  - **Returns**: None
  - **Usage**: Creates a `PromptsManager` instance to manage prompts programmatically or via CLI.
  - **Example**:
    ```python
    from utils.prompts_manager import PromptsManager
    pm = PromptsManager()  # Uses default "prompts/prompts.json"
    ```
  - **Where to Use**: Instantiate in any script, module, or class needing prompt management, such as agents, workflows, or custom tools.

- **`_load_prompts(self)`**
  - **Description**: Loads the existing prompts from the JSON file into memory. Returns an empty dictionary if the file doesn’t exist.
  - **Parameters**: None
  - **Returns**: dict - The loaded prompts.
  - **Usage**: Internal method called during initialization to populate `self.prompts`.
  - **Example**: Not called directly; used by `__init__`.
  - **Where to Use**: N/A (internal).

- **`_save_prompts(self)`**
  - **Description**: Saves the current `self.prompts` dictionary to the JSON file, creating the `prompts/` directory if it doesn’t exist.
  - **Parameters**: None
  - **Returns**: None
  - **Usage**: Internal method called after updates, deletions, or additions to persist changes.
  - **Example**: Not called directly; used by other methods.
  - **Where to Use**: N/A (internal).

- **`_update_prompt_store(self, dir: str)`**
  - **Description**: Scans a top-level directory for Python files, extracts class and function structures using AST, and updates `prompts.json` with new entries (e.g., `"no prompts"`). Preserves existing entries.
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
  - **Description**: Recursively scans a directory and subdirectories for Python files, updating `prompts.json` with proper nesting.
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
  - **Description**: Performs a hard update on a top-level directory, rebuilding its subtree in `prompts.json`, removing non-existent entries, and preserving existing prompt values.
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
  - **Description**: Recursively performs a hard update across a directory tree, preserving prompt values and removing non-existent entries.
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
  - **Description**: Adds or updates a prompt for an existing key in `prompts.json` if the key has a string value (i.e., is a prompt field).
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
  - **Description**: Deletes specified keys from `prompts.json` using dot notation and returns the list of successfully deleted keys.
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

---

### Programmatic API Usage
The `PromptsManager` class is designed for broad use across your project. Public methods like `list_prompts`, `add_prompt`, `delete_keys`, and `get_prompt` are recommended for integration into other codebases.

#### Initializing and Managing
```python
from utils.prompts_manager import PromptsManager

pm = PromptsManager()

# List prompts
keys = pm.list_prompts()
print("All keys:", keys)

# Add a prompt
pm.add_prompt("tests.t.TextClass.run", "Hello, {name}")

# Delete a key
pm.delete_keys(["tests.t.TextClass.run"])

# Get a prompt
prompt = pm.get_prompt("tests.t.TextClass.run", name="Alice")
print("Prompt:", prompt)
```

#### Example Integration
```python
class LogAgent:
    def __init__(self):
        self.pm = PromptsManager()

    def process_log(self, log_data):
        # List available prompts for debugging
        prompts = self.pm.list_prompts(only_prompts=True)
        print("Available prompts:", prompts)

        # Add a custom prompt if needed
        self.pm.add_prompt("agents.log_agent.process_log", "Analyze {data}")

        # Use the prompt
        return self.pm.get_prompt("agents.log_agent.process_log", data=log_data)

agent = LogAgent()
print(agent.process_log("error log"))  # "Analyze error log"
```

---

### Command-Line Interface (CLI)
Run from the project root where `prompts/` is a subdirectory.

#### Usage
```bash
python utils/prompts_manager.py [ACTION] [OPTIONS]
```

#### Actions and Options
- **`scan`**:
  - **Description**: Scans a directory to update `prompts.json`.
  - **Flags**:
    - `-d, --directory <DIR>` (required): Directory to scan.
    - `-r, --recursive`: Recursively scan subdirectories.
    - `--hard`: Perform a hard update, removing non-existent entries.
    - `--verbose`: Print the full `prompts.json` after scanning.
  - **Example**:
    ```bash
    python utils/prompts_manager.py scan -d tests/ -r --verbose
    ```

- **`list`**:
  - **Description**: Lists all keys or only prompt keys in `prompts.json`.
  - **Flags**:
    - `-p, --prompt`: Restrict to keys with string prompts.
    - `--verbose`: Print the full `prompts.json`.
  - **Example**:
    ```bash
    python utils/prompts_manager.py list --prompt
    ```

- **`add`**:
  - **Description**: Adds or updates a prompt for an existing key.
  - **Flags**:
    - `-k, --key <KEY>` (required): Key in dot notation.
    - `-v, --value <VALUE>` (required): New prompt string.
    - `--verbose`: Print the full `prompts.json`.
  - **Example**:
    ```bash
    python utils/prompts_manager.py add -k tests.t.TextClass.run -v "Hello, {name}"
    ```

- **`delete`**:
  - **Description**: Deletes specified keys from `prompts.json`.
  - **Flags**:
    - `-k, --key <KEY1> <KEY2> ...` (required): Keys to delete.
    - `--verbose`: Print the full `prompts.json`.
  - **Example**:
    ```bash
    python utils/prompts_manager.py delete -k tests.t.TextClass.run
    ```

- **No Arguments**:
  - **Description**: Displays the help message.
  - **Example**:
    ```bash
    python utils/prompts_manager.py
    ```

#### Directory Context
- **Run From**: Project root (e.g., `project_root/`).
- **Target Directories**: Use relative paths (e.g., `tests/`).
