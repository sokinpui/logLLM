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

    _Note_: The prompt management (`pm`) command requires `git` installed and accessible in the system PATH for version control features. Docker (or Colima on macOS) is required for the `db` command.

4.  **Set Environment Variables**:
    - Ensure `GENAI_API_KEY` is set in your environment if using the Gemini model.
    - Check `src/logllm/config/config.py` for other potential configuration needs.

The main entry point is `src/logllm/__main__.py`. Run commands using `python -m src.logllm <command> [options]`.

**For a comprehensive guide to all CLI commands, actions, options, and examples, please refer to the dedicated [CLI Documentation Hub](./doc/cli/README.md).**

**Quick Examples:**

- Start database containers: `python -m src.logllm db start`
- Collect logs: `python -m src.logllm collect -d ./logs`
- Parse local file: `python -m src.logllm parse -f ./logs/some.log`
- Parse logs in Elasticsearch for all groups: `python -m src.logllm es-parse run -t 4`
- Normalize timestamps for a group: `python -m src.logllm normalize-ts run -g apache`
- Scan for prompts: `python -m src.logllm pm scan -d src/logllm/agents -r`

Refer to the [Global Options documentation](./doc/cli/global_options.md) for options like `--verbose`, `--test`, and `--json` that apply across commands.

## Project Structure

```
logLLM/
├── doc/
│   ├── cli/                 # Detailed CLI command documentation
│   │   ├── README.md        # Navigation for CLI docs
│   │   ├── global_options.md
│   │   ├── db.md
│   │   ├── collect.md
│   │   ├── parse.md
│   │   ├── es-parse.md
│   │   ├── normalize-ts.md
│   │   └── pm.md
│   ├── agents.md
│   ├── configurations.md
│   ├── overview.md
│   ├── prompts_manager.md
│   └── utils.md
├── logs/                # Example log files
├── models/              # Local LLM model files
├── prompts/             # Default prompt store
│   └── .git/
├── src/
│   └── logllm/
│       ├── __init__.py
│       ├── __main__.py
│       ├── agents/
│       ├── cli/             # CLI command handlers
│       ├── config/
│       ├── processors/      # Data processing modules
│       └── utils/
├── .gitignore
├── pyproject.toml
├── requirement.txt
├── README.md            # This file
└── movelook.log
```

## Documentation

- **[CLI Documentation Hub](./doc/cli/README.md)**: Comprehensive guide for all CLI commands.
- **[agents.md](./doc/agents.md)**: Agent details.
- **[configurations.md](./doc/configurable.md)**: Config settings (`config.py`).
- **[utils.md](./doc/utils.md)**: Utility module documentation.
- **[prompt_manager.md](./doc/prompts_manager.md)**: Detailed guide for the `pm` command and `PromptsManager` class (also covered in CLI docs).
- **[overview.md](./doc/overview.md)**: High-level overview of CLI orchestration.

## Contributing

Contributions are welcome! Please:

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/xyz`).
3. Commit changes (`git commit -m "Add xyz feature"`).
4. Push to the branch (`git push origin feature/xyz`).
5. Open a pull request.

## License

[MIT License](./LICENSE) - feel free to use, modify, and distribute this project.
