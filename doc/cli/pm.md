# logLLM CLI: `pm` Command (Prompt Manager)

The `pm` command provides a powerful interface to manage Large Language Model (LLM) prompts used within the `logLLM` project. It interacts with the `PromptsManager` class, which stores prompts in a structured JSON file (defaulting to `prompts/prompts.json`). A key feature is its integration with Git: the directory containing the prompt file is treated as a Git repository, and every modification made via `pm` commands is automatically committed. This enables version tracking, comparison, and easy rollback of prompt changes.

**Prerequisites:**

- `git` must be installed on your system and accessible in the PATH for version control features to work.

**Base command:** `python -m src.logllm pm <action> [OPTIONS]`

**Default Prompt File:** `prompts/prompts.json`
**Test Prompt File (with global `--test`):** `prompts/test.json`
**Custom Prompt File (with global `-j PATH`):** As specified by `PATH`.

See also: [Global Options](./global_options.md) for how to change the target prompt file.

---

## Common `pm` Option

- `--verbose-pm`:
  If specified, prints the entire content of the currently targeted prompt JSON file after actions that modify it (specifically `scan`, `add`, `rm`, `revert`). This helps in visually confirming the changes.

---

## Actions

### `pm scan`

Scans Python code directories to discover potential prompt locations, which are typically identified as functions (especially methods within classes). It then updates the structure of the prompt JSON file to reflect the discovered code structure. New keys corresponding to newly found functions are initialized with a placeholder value (e.g., `"no prompts"`).

**Usage:**

```bash
python -m src.logllm pm scan -d DIRECTORY [OPTIONS]
```

**Options:**

- `-d DIRECTORY`, `--directory DIRECTORY` (Required):
  The directory path containing Python source files to scan (e.g., `src/logllm/agents`, `src/logllm/utils`).
- `-r`, `--recursive`:
  If specified, the scan will include subdirectories recursively.
- `--hard`:
  Performs a "hard" update. When scanning the specified directory's corresponding subtree in the JSON:
  - **Adds:** Keys found in the code but not present in the JSON are added.
  - **Removes:** Keys present in the JSON but no longer found in the scanned code are _removed_.
  - **Preserves:** Existing prompt string values for keys that continue to exist in both code and JSON are preserved.
    If `--hard` is _not_ used (this is the default "soft" update), keys are only added or updated if they are new; keys existing in JSON but not found in the code are left untouched.
- `-m "MESSAGE"`, `--message "MESSAGE"`:
  (Optional) Provides a custom Git commit message for the changes made by the scan operation.
  - If the flag is used with a message string (e.g., `-m "Scan agent prompts"`), that message is used.
  - If the flag is used without a message string (e.g., `-m`), it will attempt to open the default Git commit message editor.
  - If the flag is omitted entirely, a default commit message with a timestamp is automatically generated.

**Examples:**

1.  **Recursively scan the `src/logllm/agents` directory and update `prompts/prompts.json` (soft update, default commit message):**

    ```bash
    python -m src.logllm pm scan -d src/logllm/agents -r
    ```

2.  **Perform a hard, recursive scan of `src/logllm/utils` using a custom prompt file and a specific commit message:**

    ```bash
    python -m src.logllm -j my_prompts.json pm scan -d src/logllm/utils -r --hard -m "Refactor utility prompts and remove obsolete entries"
    ```

3.  **Scan `src/logllm/processors`, open editor for commit message, and show JSON after:**
    ```bash
    python -m src.logllm pm scan -d src/logllm/processors -m --verbose-pm
    ```

---

### `pm list`

Lists the keys present in the currently targeted prompt JSON file. This helps in understanding the structure and identifying keys for adding or modifying prompts.

**Usage:**

```bash
python -m src.logllm pm list [OPTIONS]
```

**Options:**

- `-p`, `--prompt`:
  If specified, the command will list only those keys that currently hold actual prompt strings (i.e., leaf nodes in the JSON structure whose values are strings). It will omit keys that represent directory, module, or class structures (which are dictionaries).

**Examples:**

1.  **List all keys (structure and prompts) in the default `prompts/prompts.json`:**

    ```bash
    python -m src.logllm pm list
    ```

2.  **List only the keys that are actual prompts in the `prompts/test.json` file:**
    ```bash
    python -m src.logllm --test pm list --prompt
    ```

---

### `pm add`

Adds a new prompt string or updates an existing prompt string for a specific key in the prompt JSON file. The key should typically correspond to a Python function (e.g., `module.class.method_name`) where `PromptsManager.get_prompt()` will be called.

**Usage:**

```bash
python -m src.logllm pm add -k KEY (-v "VALUE" | -f FILE_PATH) [OPTIONS]
```

**Required Options:**

- `-k KEY`, `--key KEY`:
  The dot-separated key path in the JSON where the prompt string should be stored. For example: `src.logllm.agents.es_parser_agent.SingleGroupParserAgent._generate_grok_node`.
- One of the following (mutually exclusive options for providing the prompt value):
  - `-v "VALUE"`, `--value "VALUE"`: The prompt string itself, provided directly on the command line.
  - `-f FILE_PATH`, `--file FILE_PATH`: The path to a text file from which the prompt string should be read.

**Optional Options:**

- `-m "MESSAGE"`, `--message "MESSAGE"`: Custom Git commit message for this addition/update. (See `pm scan` for behavior).

**Examples:**

1.  **Add a prompt string directly for a specific key:**

    ```bash
    python -m src.logllm pm add -k src.logllm.utils.llm_model.GeminiModel.generate -v "Generate content for: {input_text}"
    ```

2.  **Update the prompt for a key by reading content from `new_grok_prompt.txt` and provide a custom commit message:**
    ```bash
    python -m src.logllm pm add \
        -k src.logllm.agents.es_parser_agent.SingleGroupParserAgent._generate_grok_node \
        -f ./prompts_texts/new_grok_prompt.txt \
        -m "Update Grok generation prompt with refined instructions"
    ```

---

### `pm rm`

Removes one or more keys (and their associated values or nested dictionary structures) from the prompt JSON file.

**Usage:**

```bash
python -m src.logllm pm rm -k KEY1 [KEY2 ...] [OPTIONS]
```

**Required Options:**

- `-k KEY [KEY ...]`, `--key KEY [KEY ...]`:
  One or more dot-separated keys to be deleted from the JSON file.

**Optional Options:**

- `-m "MESSAGE"`, `--message "MESSAGE"`: Custom Git commit message.

**Example:**

```bash
# Remove two specific keys from the prompt store
python -m src.logllm pm rm \
    -k src.logllm.old_feature.OldAgent.some_method \
    -k src.logllm.another_module.DeprecatedClass \
    -m "Remove obsolete prompts for OldAgent and DeprecatedClass"
```

---

### `pm version`

Lists the Git commit history for the prompt JSON file. This command can be filtered to show only the history of changes affecting a specific prompt key.

**Usage:**

```bash
python -m src.logllm pm version [OPTIONS]
```

**Options:**

- `-k KEY`, `--key KEY`:
  (Optional) If specified, filters the history to show only those commits where the value associated with this particular dot-separated key was modified.
- `--verbose-hist [N]`:
  (Optional, applicable if `-k` is used) When displaying the version history for a specific key, this option controls how much of the prompt value is shown for each version.
  - Provide an integer `N` to show the first `N` characters (e.g., `--verbose-hist 100`).
  - Defaults to `50` characters if `N` is not given.
  - Use `--verbose-hist -1` to display the full prompt text for each version.
- `-t N`, `--tail N`:
  (Optional) Shows only the last `N` relevant commits in the history. If `N` is not provided or is `-1`, it shows all relevant commits.
- `--free`:
  If specified, uses a free-form output style instead of the default fixed-width boxed table. This can be more readable for very long commit messages or prompt texts.

**Examples:**

1.  **Show the full version history of the entire prompt file:**

    ```bash
    python -m src.logllm pm version
    ```

2.  **Show the last 3 versions where the prompt for `src.logllm.agents.es_parser_agent.SingleGroupParserAgent._generate_grok_node` changed, displaying the full prompt text for each of those versions:**
    ```bash
    python -m src.logllm pm version \
        -k src.logllm.agents.es_parser_agent.SingleGroupParserAgent._generate_grok_node \
        --verbose-hist -1 \
        -t 3
    ```

---

### `pm revert`

Reverts the state of the prompt JSON file, or a specific key within it, to how it was at a previous Git commit.

**Usage:**

```bash
python -m src.logllm pm revert -c COMMIT_HASH [OPTIONS]
```

**Required Options:**

- `-c COMMIT_HASH`, `--commit COMMIT_HASH`:
  The Git commit hash (can be a short or full hash) to which the state should be reverted.

**Optional Options:**

- `-k KEY`, `--key KEY`:
  If specified, only the prompt value for this particular dot-separated key will be reverted to its state at `COMMIT_HASH`. The rest of the prompt file remains unchanged from its current state. If this option is omitted, the _entire_ prompt JSON file is reverted to its exact content at the specified `COMMIT_HASH`.
- `--verbose-rev [N]`:
  (Optional, applicable if `-k` is used) After reverting a specific key, this option controls how much of the reverted prompt value is printed to the console.
  - Provide an integer `N` for the first `N` characters.
  - Defaults to `50` characters if `N` is not given.
  - Use `--verbose-rev -1` for the full reverted prompt.
- `-m "MESSAGE"`, `--message "MESSAGE"`: Custom Git commit message for the revert action itself.

**Examples:**

1.  **Revert the entire prompt file to its state at commit `a1b2c3d`:**

    ```bash
    python -m src.logllm pm revert -c a1b2c3d -m "Revert all prompts to state at a1b2c3d"
    ```

2.  **Revert only the prompt for the key `src.logllm.agents.parser_agent.SimpleGrokLogParserAgent._generate_grok_pattern` to its value from commit `HEAD~2` (two commits before current HEAD):**
    ```bash
    python -m src.logllm pm revert \
        -c HEAD~2 \
        -k src.logllm.agents.parser_agent.SimpleGrokLogParserAgent._generate_grok_pattern \
        --verbose-rev -1
    ```

---

### `pm diff`

Shows the differences in the content of the prompt JSON file, or for a specific prompt key, between two specified Git commits.

**Usage:**

```bash
python -m src.logllm pm diff -c1 COMMIT_HASH1 -c2 COMMIT_HASH2 [OPTIONS]
```

**Required Options:**

- `-c1 COMMIT_HASH1`, `--commit1 COMMIT_HASH1`: The first Git commit hash for comparison (often the older state).
- `-c2 COMMIT_HASH2`, `--commit2 COMMIT_HASH2`: The second Git commit hash for comparison (often the newer state). You can use Git symbolic refs like `HEAD`, `HEAD~1`, etc.

**Optional Options:**

- `-k KEY`, `--key KEY`:
  If specified, the diff will only be shown for the value of this specific dot-separated key. Otherwise, the diff will be for the entire content of the prompt JSON file.
- `--verbose-diff [N]`:
  (Optional) Controls the amount of text shown for differing prompt values or JSON content in the diff output.
  - Provide an integer `N` for the first `N` characters.
  - Defaults to `50` characters if `N` is not given.
  - Use `--verbose-diff -1` to show the full differing content.

**Examples:**

1.  **Show differences for the entire prompt file between the previous commit (`HEAD~1`) and the current commit (`HEAD`):**

    ```bash
    python -m src.logllm pm diff -c1 HEAD~1 -c2 HEAD --verbose-diff 200
    ```

2.  **Show the differences specifically for the prompt key `app.feature.AgentX.process_data` between commits `a1b2c3d` and `e4f5g6h`, displaying the full text of the differing prompts:**
    ```bash
    python -m src.logllm pm diff \
        -c1 a1b2c3d \
        -c2 e4f5g6h \
        -k app.feature.AgentX.process_data \
        --verbose-diff -1
    ```
