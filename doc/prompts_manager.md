## File: `prompts_manager.py`

### Class: `PromptsManager`
- **Purpose**: Manages a JSON-based prompt store (`prompts.json`) for storing and retrieving prompts associated with Python code structures (directories, modules, classes, and functions). It supports scanning directories to populate the store, deleting keys, listing keys, adding/updating prompts, and retrieving prompts with placeholder substitution.
- **Location**: Recommended to place this file in a `utils/` directory within your project (e.g., `project_root/utils/prompts_manager.py`), as it serves as a utility for other modules.
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
  - **Where to Use**: Use in any script, module, or class needing prompt management, typically initialized once per application or instance.

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
  - **Example**: Not called directly; used by `_update_prompt_store`, `_hard_update_prompt_store`, `delete_keys`, `_add_prompt`.
  - **Where to Use**: N/A (internal).

- **`_update_prompt_store(self, dir: str)`**
  - **Description**: Scans a top-level directory for Python files, extracts class and function structures using AST, and updates `prompts.json` with new entries (e.g., `"no prompts"`). Preserves existing entries.
  - **Parameters**:
    - `dir` (str): Directory path to scan (e.g., `"tests/"`).
  - **Returns**: List[str] - Keys added or modified (e.g., `["tests.t.TextClass.run"]`).
  - **Usage**: Run this to populate or refresh the prompt store after adding new Python files or modifying existing ones non-recursively.
  - **Example**:
    ```python
    pm = PromptsManager()
    updated = pm._update_prompt_store("tests/")
    print(updated)  # e.g., ["tests.t", "tests.t.TextClass", "tests.t.TextClass.run"]
    ```
  - **Where to Use**: Use in scripts or CLI tools to initialize or update `prompts.json` for a single directory. Typically run from the project root.

- **`_update_prompt_store_recursive(self, dir: str, current_dict: Dict[str, Any] = None, base_path: str = "")`**
  - **Description**: Recursively scans a directory and its subdirectories for Python files, updating `prompts.json` with proper nesting. Skips hidden directories and `__pycache__`.
  - **Parameters**:
    - `dir` (str): Directory path to scan (e.g., `"tests/"`).
    - `current_dict` (Dict[str, Any], optional): Current dictionary level (internal recursion).
    - `base_path` (str, optional): Base path for key construction (internal recursion).
  - **Returns**: List[str] - Keys added or modified (e.g., `["tests.subdir.nested.NestedClass.run"]`).
  - **Usage**: Use for recursive updates across a directory tree.
  - **Example**:
    ```python
    pm = PromptsManager()
    updated = pm._update_prompt_store_recursive("tests/")
    print(updated)  # e.g., ["tests.t.TextClass.run", "tests.subdir.nested.NestedClass.run"]
    ```
  - **Where to Use**: Use programmatically or via CLI with `-r` to update `prompts.json` for nested directory structures.

- **`_hard_update_prompt_store(self, dir: str)`**
  - **Description**: Performs a hard update on a top-level directory, rebuilding its subtree in `prompts.json` to match current Python files, removing non-existent entries, and preserving existing prompt values.
  - **Parameters**:
    - `dir` (str): Directory path to scan (e.g., `"tests/"`).
  - **Returns**: List[str] - Keys in the updated subtree (e.g., `["tests.t.TextClass.run"]`).
  - **Usage**: Use to synchronize `prompts.json` with the current state of a directory, clearing outdated entries.
  - **Example**:
    ```python
    pm = PromptsManager()
    updated = pm._hard_update_prompt_store("tests/")
    print(updated)  # e.g., ["tests.t", "tests.t.TextClass", "tests.t.TextClass.run"]
    ```
  - **Where to Use**: Use in maintenance scripts or CLI with `--hard` to clean up a single directory’s entries.

- **`_hard_update_prompt_store_recursive(self, dir: str, current_dict: Dict[str, Any] = None, base_path: str = "")`**
  - **Description**: Recursively performs a hard update, rebuilding the subtree for the given directory and its subdirectories, preserving prompt values and removing non-existent entries.
  - **Parameters**:
    - `dir` (str): Directory path to scan (e.g., `"tests/"`).
    - `current_dict` (Dict[str, Any], optional): Current dictionary level (internal recursion).
    - `base_path` (str, optional): Base path for key construction (internal recursion).
  - **Returns**: List[str] - Keys in the updated subtree (e.g., `["tests.subdir.nested.NestedClass.run"]`).
  - **Usage**: Use for recursive cleanup of a directory tree.
  - **Example**:
    ```python
    pm = PromptsManager()
    updated = pm._hard_update_prompt_store_recursive("tests/")
    print(updated)  # e.g., ["tests.t.TextClass.run", "tests.subdir.nested.NestedClass.run"]
    ```
  - **Where to Use**: Use programmatically or via CLI with `-r --hard` to synchronize nested directories.

- **`_list_prompts(self, only_prompts: bool = False)`**
  - **Description**: Lists all keys in `prompts.json` or only those with string prompt values, returning them as a list of lists. Prints keys in a format matching update functions.
  - **Parameters**:
    - `only_prompts` (bool): If `True`, only list keys with string values (prompts); if `False`, list all keys (default: `False`).
  - **Returns**: List[List[str]] - Keys as lists (e.g., `[["tests"], ["tests", "t", "TextClass", "run"]]`) .
  - **Usage**: Use to inspect the current state of `prompts.json` programmatically or via CLI.
  - **Example**:
    ```python
    pm = PromptsManager()
    all_keys = pm._list_prompts()  # All keys
    prompt_keys = pm._list_prompts(only_prompts=True)  # Only prompt keys
    print(all_keys)  # [["tests"], ["tests", "t"], ["tests", "t", "TextClass"], ["tests", "t", "TextClass", "run"]]
    print(prompt_keys)  # [["tests", "t", "TextClass", "run"]]
    ```
  - **Where to Use**: Use in scripts for debugging or analysis, or via CLI with `list` action.

- **`_add_prompt(self, key: str, value: str)`**
  - **Description**: Adds or updates a prompt for an existing key in `prompts.json` if the key already has a string value (i.e., is a prompt field).
  - **Parameters**:
    - `key` (str): Dot-notation key (e.g., `"tests.t.TextClass.run"`).
    - `value` (str): New prompt value (e.g., `"Hello, {name}"`).
  - **Returns**: bool - `True` if successful, `False` if the key doesn’t exist or isn’t a prompt field.
  - **Usage**: Use to manually set or update prompt values in `prompts.json`.
  - **Example**:
    ```python
    pm = PromptsManager()
    success = pm._add_prompt("tests.t.TextClass.run", "Hello, {name}")
    print(success)  # True if key exists and is a string field
    ```
  - **Where to Use**: Use in scripts or via CLI with `add` action to customize prompts.

- **`delete_keys(self, keys: list[str])`**
  - **Description**: Deletes specified keys from `prompts.json` using dot notation and returns the list of successfully deleted keys.
  - **Parameters**:
    - `keys` (list[str]): List of keys to delete (e.g., `["tests.t.TextClass.run"]`).
  - **Returns**: List[str] - Keys that were deleted.
  - **Usage**: Use to remove outdated or unwanted prompts or structural entries from the store.
  - **Example**:
    ```python
    pm = PromptsManager()
    deleted = pm.delete_keys(["tests.t.TextClass.run"])
    print(deleted)  # ["tests.t.TextClass.run"]
    ```
  - **Where to Use**: Use in maintenance scripts or CLI tools to clean up `prompts.json`.

- **`get_prompt(self, metadata: str = None, **variables: str) -> str`**
  - **Description**: Retrieves a prompt from `prompts.json` using either a provided metadata string or runtime-resolved metadata (directory.module.class.function). Substitutes placeholders (e.g., `{msg}`) with provided variables.
  - **Parameters**:
    - `metadata` (str, optional): Dot-separated path to the prompt (e.g., `"tests.t.TextClass.run"`). If `None`, resolved at runtime.
    - `**variables` (str): Keyword arguments mapping placeholder names to values (e.g., `msg="hello"`).
  - **Returns**: str - The prompt with placeholders replaced.
  - **Raises**:
    - `KeyError`: If the prompt isn’t found.
    - `ValueError`: If placeholders and variables mismatch.
    - `RuntimeError`: If runtime metadata resolution fails (e.g., not called from a class method).
  - **Usage**: Call this within a class method to fetch a prompt dynamically or with a specific path for manual control.
  - **Example**:
    ```python
    class TextClass:
        def __init__(self):
            self.pm = PromptsManager()

        def run(self):
            prompt = self.pm.get_prompt(msg="hello", msg2="world")  # Runtime: "tests.t.TextClass.run"
            print(prompt)  # e.g., "hello, world"

    # Manual metadata
    pm = PromptsManager()
    prompt = pm.get_prompt("tests.t.TextClass.run", msg="hi", msg2="there")
    print(prompt)  # "hi, there"
    ```
  - **Where to Use**: Use in application logic (e.g., inside classes like `TextClass`) to retrieve prompts for processing or display. Place `prompts_manager.py` in `utils/` and import it where needed.

---

### Programmatic API Usage
The `PromptsManager` class provides a flexible API for managing prompts programmatically. Below are examples of how to use each method:

#### Initializing and Updating
```python
from utils.prompts_manager import PromptsManager

# Initialize
pm = PromptsManager()

# Update non-recursively
updated_keys = pm._update_prompt_store("tests/")
print("Updated keys:", updated_keys)

# Update recursively
updated_keys = pm._update_prompt_store_recursive("tests/")
print("Updated keys:", updated_keys)

# Hard update non-recursively
updated_keys = pm._hard_update_prompt_store("tests/")
print("Hard updated keys:", updated_keys)

# Hard update recursively
updated_keys = pm._hard_update_prompt_store_recursive("tests/")
print("Hard updated keys:", updated_keys)
```

#### Listing Keys
```python
# List all keys
all_keys = pm._list_prompts()
print("All keys:", all_keys)

# List only prompt keys
prompt_keys = pm._list_prompts(only_prompts=True)
print("Prompt keys:", prompt_keys)
```

#### Adding/Updating Prompts
```python
# Add or update a prompt
success = pm._add_prompt("tests.t.TextClass.run", "Hello, {name}")
if success:
    print("Prompt updated successfully")
else:
    print("Failed to update prompt")
```

#### Deleting Keys
```python
# Delete keys
deleted = pm.delete_keys(["tests.t.TextClass.run", "tests.subdir.nested"])
print("Deleted keys:", deleted)
```

#### Retrieving Prompts
```python
# Manual retrieval
prompt = pm.get_prompt("tests.t.TextClass.run", name="Alice")
print("Manual prompt:", prompt)

# Runtime retrieval within a class
class TextClass:
    def __init__(self):
        self.pm = PromptsManager()

    def run(self):
        return self.pm.get_prompt(name="Bob")  # Resolves to "tests.t.TextClass.run"

obj = TextClass()
print("Runtime prompt:", obj.run())
```

---

### Command-Line Interface (CLI)
The `prompts_manager.py` file includes a `main()` function that provides a CLI for managing `prompts.json`. Run it from the project root directory where `prompts/` is a subdirectory.

#### Usage
```bash
python prompts_manager.py [ACTION] [OPTIONS]
```

#### Actions and Options
- **`list`**:
  - **Description**: Lists all keys in `prompts.json` or only those with prompt strings.
  - **Flags**:
    - `--prompt`: Restrict output to keys with string prompt values.
  - **Examples**:
    ```bash
    python prompts_manager.py list
    ```
    **Output**:
    ```
    Keys in prompts.json:
      - tests
      - tests.t
      - tests.t.TextClass
      - tests.t.TextClass.run
      - tests.subdir
      - tests.subdir.nested
      - tests.subdir.nested.NestedClass
      - tests.subdir.nested.NestedClass.run
    ```
    ```bash
    python prompts_manager.py list --prompt
    ```
    **Output**:
    ```
    Keys in prompts.json (prompts only):
      - tests.t.TextClass.run
      - tests.subdir.nested.NestedClass.run
    ```
  - **When to Use**: To inspect the current contents of `prompts.json`.

- **`add`**:
  - **Description**: Adds or updates a prompt for an existing key that has a string value.
  - **Flags**:
    - `-k, --key <KEY>`: The key in dot notation (e.g., `"tests.t.TextClass.run"`).
    - `-v, --value <VALUE>`: The new prompt string (e.g., `"Hello, {name}"`).
  - **Examples**:
    ```bash
    python prompts_manager.py add -k tests.t.TextClass.run -v "Hello, {name}"
    ```
    **Output**:
    ```
    Added/Updated prompt for 'tests.t.TextClass.run': 'Hello, {name}'
    ```
    ```bash
    python prompts_manager.py add -k tests.t.TextClass -v "Invalid"
    ```
    **Output**:
    ```
    Error: Key 'tests.t.TextClass' does not exist or is not a prompt field
    ```
  - **When to Use**: To manually set or update prompt values without editing `prompts.json` directly.

- **`-d, --directory <DIR>`**:
  - **Description**: Scans the specified directory and updates `prompts.json` with new Python file structures.
  - **Flags**:
    - `-r, --recursive`: Recursively scan subdirectories.
    - `--hard`: Perform a hard update, removing non-existent entries within the directory.
  - **Examples**:
    ```bash
    python prompts_manager.py -d tests/
    ```
    **Output**:
    ```
    Updated keys in prompts.json from tests/:
      - tests.t
      - tests.t.TextClass
      - tests.t.TextClass.run
    ```
    ```bash
    python prompts_manager.py -d tests/ -r
    ```
    **Output**:
    ```
    Updated keys in prompts.json from tests/:
      - tests.t.TextClass.run
      - tests.subdir.nested.NestedClass.run
    ```
    ```bash
    python prompts_manager.py -d tests/ -r --hard
    ```
    **Output**:
    ```
    Updated keys in prompts.json from tests/:
      - tests.t.TextClass.run
      - tests.subdir.nested.NestedClass.run
    ```
  - **When to Use**: After adding or modifying Python files to refresh `prompts.json`.

- **`--delete <KEY1> <KEY2> ...`**:
  - **Description**: Deletes one or more keys from `prompts.json` using dot notation.
  - **Example**:
    ```bash
    python prompts_manager.py --delete tests.t.TextClass.run
    ```
    **Output**:
    ```
    Deleted 'tests.t.TextClass.run' from prompts
    Deleted keys from prompts.json:
      - tests.t.TextClass.run
    ```
  - **When to Use**: To remove specific prompts or clean up unused entries.

- **No Arguments**:
  - **Description**: Displays the help message if no action or options are provided.
  - **Example**:
    ```bash
    python prompts_manager.py
    ```
    **Output**:
    ```
    usage: prompts_manager.py [-h] [-d DIRECTORY] [-r] [--hard] [--delete DELETE [DELETE ...]] [--prompt] [-k KEY] [-v VALUE] [action]

    Manage prompts in prompts.json: update, hard update, delete, list, or add prompts.

    positional arguments:
      action                Action to perform: 'list' to list keys, 'add' to add a prompt

    optional arguments:
      -h, --help            show this help message and exit
      -d DIRECTORY, --directory DIRECTORY
                            Directory to scan and add to prompts.json (e.g., tests/)
      -r, --recursive       Recursively scan subdirectories, skipping hidden dirs and __pycache__
      --hard                Perform a hard update: clear non-existent objects within the given directory, keep existing values
      --delete DELETE [DELETE ...]
                            Keys to delete from prompts.json in dot notation (e.g., 'tests.t.TextClass.fa')
      --prompt              With 'list', only show keys with prompt strings
      -k KEY, --key KEY     With 'add', the key to update in dot notation (e.g., 'tests.t.TextClass.run')
      -v VALUE, --value VALUE
                            With 'add', the string value to assign to the key
    ```

#### Directory Context
- **Run From**: Execute the script from the project root (e.g., `project_root/`), where `prompts/prompts.json` is expected relative to the working directory.
- **Target Directories**: Pass relative paths (e.g., `tests/`, `tests/subdir/`) to scan subdirectories containing Python files.

---

### Usage Notes
- **Project Structure**:
  - Place `prompts_manager.py` in `utils/` (e.g., `project_root/utils/prompts_manager.py`).
  - Store `prompts.json` in `project_root/prompts/prompts.json` (default path).
  - Organize Python files in subdirectories like `tests/`, `agents/`, etc., for scanning.

- **Setup**:
  - Before using `get_prompt`, run `python prompts_manager.py -d <directory>` or `-r` to populate `prompts.json` with your code structure.
  - Use `add` or manually edit `prompts.json` to replace `"no prompts"` with actual prompt strings (e.g., `"Hello, {name}"`).

- **Example Workflow**:
  1. Create `tests/t.py`:
     ```python
     class TextClass:
         def run(self):
             pass
     ```
  2. Scan and update:
     ```bash
     python prompts_manager.py -d tests/ -r
     ```
  3. Add a prompt:
     ```bash
     python prompts_manager.py add -k tests.t.TextClass.run -v "Hello, {name}"
     ```
  4. List prompts:
     ```bash
     python prompts_manager.py list --prompt
     ```
  5. Use in code:
     ```python
     from utils.prompts_manager import PromptsManager
     pm = PromptsManager()
     print(pm.get_prompt("tests.t.TextClass.run", name="Alice"))  # "Hello, Alice"
     ```
