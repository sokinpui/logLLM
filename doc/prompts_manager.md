# Prompts Management System

The `logLLM` project includes a robust system for managing Large Language Model (LLM) prompts. This system is built around two main components:

1.  **A `PromptsManager` utility class** (`src/logllm/utils/prompts_manager.py`):

    - This class provides the core logic for storing prompts in a structured JSON file (e.g., `prompts/prompts.json` by default, or `prompts/test.json` if `--test` global CLI flag is used, or a custom path via `--json <PATH>`).
    - It integrates with Git for version control of the prompt file, automatically committing changes. This enables tracking, comparison, and reversion of prompt modifications.
    - It offers a programmatic API (`get_prompt`, `add_prompt`, etc.) for agents and other parts of the system to retrieve and use prompts dynamically, including placeholder substitution (e.g., `{variable_name}`).
    - **Detailed documentation for the `PromptsManager` class itself can be found in [./utils/prompts_manager_utility.md](./utils/prompts_manager_utility.md).**

2.  **A `pm` CLI command** (`python -m src.logllm pm ...`):
    - This command-line interface allows users to interact with the `PromptsManager` to:
      - Scan Python codebases to discover and structure potential prompt locations (`pm scan`).
      - List existing prompts and their keys (`pm list`).
      - Add new prompts or update existing ones (`pm add`).
      - Delete prompts (`pm rm`).
      - Manage prompt versions by viewing history (`pm version`), reverting to previous states (`pm revert`), and comparing different versions (`pm diff`).
    - **Detailed documentation for the `pm` CLI command and its subcommands can be found in [./cli/pm.md](./cli/pm.md).**

This dual approach provides both programmatic flexibility for internal system use and a user-friendly CLI for managing the prompt lifecycle effectively.

## Key Features

- **Centralized Storage**: Prompts are organized in a JSON file, mapping them to code structures (directory/module/class/function).
- **Code Scanning**: The `pm scan` command automatically analyzes Python code to identify potential prompt locations and initialize them in the JSON file.
- **Git Version Control**: The directory containing the prompt JSON file is treated as a Git repository. All modifications made through `pm` commands or relevant `PromptsManager` methods are automatically committed, allowing for robust versioning.
- **Dynamic Prompt Retrieval**: The `PromptsManager.get_prompt()` method allows agents to fetch prompts by metadata (which can be auto-resolved based on the caller's context) and substitute variables at runtime.
- **Flexible Configuration**: The active prompt file can be easily switched using global CLI flags (`--test`, `--json`).

## Best Practices

- When using the `PromptsManager` programmatically within agents, ensure the correct prompt file path is passed if not using the default.
- Use descriptive commit messages when prompted by `pm` commands (or provide them via the `-m` option) to maintain a clear history of prompt changes.
- Consider adding the prompts directory (e.g., `prompts/`) to your main project's `.gitignore` if you prefer not to have a nested Git repository, unless you intend to manage it as a submodule.
