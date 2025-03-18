## File: `prompts_manager.py`

### Class: `PromptsManager`
- **Purpose**: Manages a JSON-based prompt store (`prompts.json`) for storing and retrieving prompts associated with Python code structures (directories, modules, classes, and functions). It supports scanning directories to populate the store, deleting keys, and retrieving prompts with placeholder substitution.
- **Location**: Recommended to place this file in a `utils/` directory within your project (e.g., `project_root/utils/prompts_manager.py`), as it serves as a utility for other modules.
- **Dependencies**: Requires Python standard libraries (`os`, `ast`, `json`, `argparse`, `re`, `inspect`).

#### Key Methods:
- **`__init__(self, json_file: str = "prompts/prompts.json")`**
  - **Description**: Initializes the `PromptsManager` with a specified JSON file path where prompts are stored. Loads existing prompts if the file exists.
  - **Parameters**:
    - `json_file` (str): Path to the JSON file (default: `"prompts/prompts.json"`).
  - **Returns**: None
  - **Usage**: Creates a `PromptsManager` instance to manage prompts.
  - **Example**:
    ```python
    from utils.prompts_manager import PromptsManager
    pm = PromptsManager()  # Uses default "prompts/prompts.json"
    ```
  - **Where to Use**: Use in any script or module needing prompt management, typically initialized once per application or class instance.

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
  - **Usage**: Internal method called after updates or deletions to persist changes.
  - **Example**: Not called directly; used by `_update_prompt_store` and `delete_keys`.
  - **Where to Use**: N/A (internal).

- **`_update_prompt_store(self, dir: str)`**
  - **Description**: Scans a directory for Python files, extracts class and function structures using AST, and updates `prompts.json` with new entries (e.g., `"no prompts"`). Returns a list of updated keys.
  - **Parameters**:
    - `dir` (str): Directory path to scan (e.g., `"tests/"`).
  - **Returns**: List[str] - Keys added or modified (e.g., `["tests.t.TextClass.fa"]`).
  - **Usage**: Run this to populate or refresh the prompt store after adding new Python files or modifying existing ones.
  - **Example**:
    ```python
    pm = PromptsManager()
    updated = pm._update_prompt_store("tests/")
    print(updated)  # e.g., ["tests.t.TextClass", "tests.t.TextClass.fa"]
    ```
  - **Where to Use**: Use in a script or CLI tool to initialize or update `prompts.json`. Typically run from the project root.

- **`delete_keys(self, keys: list[str])`**
  - **Description**: Deletes specified keys from `prompts.json` using dot notation (e.g., `"tests.t.TextClass.fa"`) and returns the list of successfully deleted keys.
  - **Parameters**:
    - `keys` (list[str]): List of keys to delete.
  - **Returns**: List[str] - Keys that were deleted.
  - **Usage**: Use to remove outdated or unwanted prompts from the store.
  - **Example**:
    ```python
    pm = PromptsManager()
    deleted = pm.delete_keys(["tests.t.TextClass.fa"])
    print(deleted)  # ["tests.t.TextClass.fa"]
    ```
  - **Where to Use**: Use in maintenance scripts or CLI tools to clean up `prompts.json`.

- **`get_prompt(self, metadata: str = None, **variables: str) -> str`**
  - **Description**: Retrieves a prompt from `prompts.json` using either a provided metadata string or runtime-resolved metadata (directory.module.class.function). Substitutes placeholders (e.g., `{msg}`) with provided variables.
  - **Parameters**:
    - `metadata` (str, optional): Dot-separated path to the prompt (e.g., `"tests.t.TextClass.fa"`). If `None`, resolved at runtime.
    - `**variables` (str): Keyword arguments mapping placeholder names to values (e.g., `msg="hello"`).
  - **Returns**: str - The prompt with placeholders replaced.
  - **Raises**:
    - `KeyError`: If the prompt isn’t found.
    - `ValueError`: If placeholders and variables mismatch.
    - `RuntimeError`: If runtime metadata resolution fails.
  - **Usage**: Call this within a class method to fetch a prompt dynamically or with a specific path for manual control. if this method is called within a class method, the metadata will resolve automatically provided the it is being managed and store properly in `prompt.json`
  - **Example**:
    ```python
    class TextClass:
        def __init__(self):
            self.pm = PromptsManager()

        def fa(self):
            msg = "hello"
            msg2 = "world"
            prompt = self.pm.get_prompt(msg=msg, msg2=msg2)  # Runtime: "tests.t.TextClass.fa"
            print(prompt)  # "hello, world"

    # Manual metadata
    pm = PromptsManager()
    prompt = pm.get_prompt("tests.t.TextClass.fa", msg="hi", msg2="there")
    print(prompt)  # "hi, there"
    ```
  - **Where to Use**: Use in application logic (e.g., inside classes like `TextClass`) to retrieve prompts for processing or display. Place `prompts_manager.py` in `utils/` and import it where needed.

---

### Command-Line Interface (CLI)
The `prompts_manager.py` file includes a `main()` function that provides a CLI for managing `prompts.json`. Run it from the project root directory where `prompts/` is a subdirectory.

#### Usage
every time you add a new python file or modify an existing one, you can run the following command to update the `prompts.json` file, to keep prompt being easy to import
```bash
python prompts_manager.py [OPTIONS]
```

#### Options
- **`-d, --directory <DIR>`**:
  - **Description**: Scans the specified directory and updates `prompts.json` with new Python file structures.
  - **Example**:
    ```bash
    python prompts_manager.py -d tests/
    ```
    **Output**:
    ```
    Updated keys in prompts.json from tests/:
      - tests.t
      - tests.t.TextClass
      - tests.t.TextClass.fa
    ```
  - **When to Use**: After adding new Python files or modifying existing ones to refresh the prompt store.

- **`--delete <KEY1> <KEY2> ...`**:
  - **Description**: Deletes one or more keys from `prompts.json` using dot notation.
  - **Example**:
    ```bash
    python prompts_manager.py --delete tests.t.TextClass.fa
    ```
    **Output**:
    ```
    Deleted 'tests.t.TextClass.fa' from prompts
    Deleted keys from prompts.json:
      - tests.t.TextClass.fa
    ```
  - **When to Use**: To remove specific prompts or clean up unused entries.

- **No Arguments**:
  - **Description**: Displays the help message if no options are provided.
  - **Example**:
    ```bash
    python prompts_manager.py
    ```
    **Output**:
    ```
    usage: prompts_manager.py [-h] [-d DIRECTORY] [--delete DELETE [DELETE ...]]

    Manage prompts in prompts.json by scanning directories or deleting keys.

    optional arguments:
      -h, --help            show this help message and exit
      -d DIRECTORY, --directory DIRECTORY
                            Directory to scan and add to prompts.json (e.g., agents/)
      --delete DELETE [DELETE ...]
                            Keys to delete from prompts.json in dot notation (e.g., 'agents agents.reasoning_agent')
    ```

#### Directory Context
- **Run From**: Execute the script from the project root (e.g., `project_root/`), where `prompts/prompts.json` is expected to reside relative to the script’s working directory.
- **Target Directories**: Pass relative paths (e.g., `tests/`, `new_tests/`) to scan subdirectories containing Python files.

---

### Usage Notes
- **Project Structure**:
  - Place `prompts_manager.py` in `utils/` (e.g., `project_root/utils/prompts_manager.py`).
  - Store `prompts.json` in `project_root/prompts/prompts.json` (default path).
  - Organize Python files in subdirectories like `tests/`, `agents/`, etc., for scanning.

- **Setup**:
  - Before using `get_prompt`, run `python prompts_manager.py -d <directory>` to populate `prompts.json` with your code structure.
  - Manually edit `prompts.json` to replace `"no prompts"` with actual prompt strings (e.g., `"{msg}, {msg2}"`).

- **Example Workflow**:
  1. Create `tests/t.py` with a class and function.
  2. Run `python prompts_manager.py -d tests/` to scan and update `prompts.json`.
  3. Edit `prompts.json` to add a prompt: `"tests.t.TextClass.fa": "{msg}, {msg2}"`.
  4. Use in code:
     ```python
     from utils.prompts_manager import PromptsManager
     pm = PromptsManager()
     print(pm.get_prompt("tests.t.TextClass.fa", msg="hello", msg2="world"))  # "hello, world"
     ```

- **Scalability**:
  - Suitable for projects with many Python files; `_update_prompt_store` only adds new keys, preserving existing prompts.
  - Use `delete_keys` to manage growth if `prompts.json` becomes cluttered.

- **Error Handling**:
  - CLI provides warnings for invalid directories or missing keys.
  - `get_prompt` raises exceptions for missing prompts or variable mismatches, aiding debugging.

- **Renaming and Moving**:
  - `get_prompt` with `metadata=None` adapts to file moves or function renames after rescanning, as it resolves the full path (`tests.t.TextClass.fa`) at runtime.

