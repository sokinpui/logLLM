# Project logLLM

**logLLM** is a command-line tool and library designed to process, parse, and analyze log data using Large Language Models (LLMs) and traditional parsing techniques. It provides a modular framework integrating various utilities and agents, managed through a central Command Line Interface (CLI).

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
- [Usage (CLI)](#usage-cli)
  - [Database Management (`db`)](#database-management-db)
  - [Log Collection (`collect`)](#log-collection-collect)
  - [File-based Parsing (`parse`)](#file-based-parsing-parse)
  - [Elasticsearch-based Parsing (`es-parse`)](#elasticsearch-based-parsing-es-parse)
  - [Prompt Management (`pm`)](#prompt-management-pm)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Overview
This project leverages a CLI built with `argparse` to manage different functionalities:

- **Database Containers**: Start, stop, and manage Elasticsearch & Kibana Docker containers (`db` command).
- **Log Collection**: Collect log files from directories and ingest them into Elasticsearch (`collect` command).
- **Log Parsing (File-based)**: Parse local log files using Grok patterns (potentially LLM-generated) and output structured data to CSV files (`parse` command).
- **Log Parsing (Elasticsearch-based)**: Parse raw logs already stored in Elasticsearch, generate/validate Grok patterns using LLMs, handle retries, and index structured results (or fallback data) into separate Elasticsearch indices (`es-parse` command).
- **Prompt Management**: A tool (`pm` command) using `PromptsManager` to generate, store, manage, and version-control LLM prompts in a JSON file (default: `prompts/prompts.json`), integrated with Git for version tracking.
- **Core Utilities**: Helper classes for database interaction, logging, data structures, LLM interaction, container management, etc. (see [utils.md](./doc/utils.md)).
- **Agents**: Underlying logic for parsing and analysis, often using `langgraph` for workflow definition (see [agents.md](./doc/agents.md)).
- **Configurations**: Centralized settings (`config.py`) for logging, Docker, databases, index naming, and LLM models (see [configurations.md](./doc/configurable.md)).

## Installation
1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/yourusername/logLLM.git # Replace with your repo URL
    cd logLLM
    ```

2.  **Set Up a Virtual Environment** (optional but recommended):
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirement.txt
    ```
    *Note*: The prompt management (`pm`) command requires `git` installed and accessible in the system PATH for version control features. Docker (or Colima on macOS) is required for the `db` command.

4.  **Set Environment Variables**:
    *   Ensure `GENAI_API_KEY` is set in your environment if using the Gemini model.
    *   Check `src/logllm/config/config.py` for other potential configuration needs.

## Usage (CLI)
The main entry point is `src/logllm/__main__.py`. Run commands using `python -m src.logllm <command> [options]`.

**Global Options:**
*   `--verbose`: Enable detailed logging output globally.
*   `--test`: Use `prompts/test.json` for prompt-related commands (`pm`, `parse`, `es-parse`). Overridden by `--json`.
*   `-j, --json PATH`: Specify a custom JSON file path for prompts. Overrides `--test`.

### Database Management (`db`)
Manage Elasticsearch and Kibana containers.
```bash
# Start containers (specify memory for Colima VM if needed)
python -m src.logllm db start [-m <GB>]

# Check container status
python -m src.logllm db status

# Stop containers
python -m src.logllm db stop [--remove] [--stop-colima]

# Restart containers
python -m src.logllm db restart [-m <GB>]
```
See `python -m src.logllm db --help` for more details.

### Log Collection (`collect`)
Collect logs from a directory into Elasticsearch. Requires a running DB.
```bash
# Collect logs from ./logs directory
python -m src.logllm collect -d ./logs
```
See `python -m src.logllm collect --help`.

### File-based Parsing (`parse`)
Parse local log files into CSV using Grok. Requires logs to be collected first if using directory mode (`-d`).
```bash
# Parse logs for groups defined in DB, based on original log directory
# Uses parallel workers by default if -t > 1
python -m src.logllm parse -d ./logs [-t <threads>] [--show-progress]

# Parse a single file (LLM generates pattern if --grok-pattern omitted)
python -m src.logllm parse -f ./logs/ssh/SSH.log [--grok-pattern "<GROK_STRING>"]
```
See `python -m src.logllm parse --help`.

### Elasticsearch-based Parsing (`es-parse`)
Parse raw logs stored in Elasticsearch, indexing results back into ES. Requires a running DB and collected logs.
```bash
# Parse all log groups found in Elasticsearch (parallel workers)
python -m src.logllm es-parse [-t <threads>] [-b <batch_size>] [-s <gen_sample>] \
                              [--validation-sample-size <val_sample>] \
                              [--validation-threshold <rate>] [--max-retries <num>] \
                              [--copy-fields <field1> <field2>] [--keep-unparsed]

# Parse only a specific group
python -m src.logllm es-parse -g <group_name> [options...]
```
See `python -m src.logllm es-parse --help`.

### Prompt Management (`pm`)
Manage LLM prompts stored in `prompts.json` (or custom path via global `-j/--json` or `--test`).
```bash
# Scan code directory to update prompt structure (recursive)
python -m src.logllm pm scan -d src/logllm/agents -r [-m "Commit message"]

# List all keys
python -m src.logllm pm list

# List only keys with actual prompts
python -m src.logllm pm list --prompt

# Add or update a prompt for a key (use -f for file input)
python -m src.logllm pm add -k src.logllm.agents.parser_agent.SimpleGrokLogParserAgent._generate_grok_pattern -v "New prompt {sample_logs}"

# Remove a key
python -m src.logllm pm rm -k src.logllm.agents.parser_agent.SimpleGrokLogParserAgent._generate_grok_pattern

# View version history for a key
python -m src.logllm pm version -k <key_path> [--verbose-hist -1] [--tail 5]

# Revert a key (or entire file if -k omitted) to a specific commit
python -m src.logllm pm revert -c <commit_hash> [-k <key_path>]

# Show differences between two commits for a key (or entire file)
python -m src.logllm pm diff -c1 <commit1> -c2 <commit2> [-k <key_path>]
```
See `python -m src.logllm pm --help` and [prompt_manager.md](./doc/prompts_manager.md) for full details.

## Project Structure
```
logLLM/
├── doc/                 # Documentation files
├── logs/                # Example log files (Input for `collect`, `parse`)
├── models/              # Local LLM model files (e.g., GGUF for llama-cpp)
├── prompts/             # Default prompt store (prompts.json, test.json - Git-managed)
│   └── .git/            # Separate Git repo for prompt versioning
├── src/
│   └── logllm/
│       ├── __init__.py
│       ├── __main__.py      # Main CLI entry point
│       ├── agents/          # Agent implementations (parsing, analysis)
│       ├── cli/             # CLI command handlers (db, collect, parse, es-parse, pm)
│       ├── config/          # Configuration (config.py)
│       └── utils/           # Utility modules (database, logger, prompts_manager, etc.)
├── .gitignore
├── pyproject.toml       # Project metadata and build config
├── requirement.txt      # Python dependencies
├── README.md            # This file
└── movelook.log         # Default log output file
```

## Documentation
- **[agents.md](./doc/agents.md)**: Agent details.
- **[configurations.md](./doc/configurable.md)**: Config settings (`config.py`).
- **[utils.md](./doc/utils.md)**: Utility module documentation.
- **[prompt_manager.md](./doc/prompts_manager.md)**: Detailed guide for the `pm` command and `PromptsManager` class.
- **[overview.md](./doc/overview.md)**: High-level overview of agent interaction (Note: Orchestration is now mainly via CLI dispatch).

## Contributing
Contributions are welcome! Please:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/xyz`).
3. Commit changes (`git commit -m "Add xyz feature"`).
4. Push to the branch (`git push origin feature/xyz`).
5. Open a pull request.

## License
[MIT License](./LICENSE) - feel free to use, modify, and distribute this project.


