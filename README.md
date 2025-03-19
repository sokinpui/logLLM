# Project logLLM

**logLLM** is a multi-agent system designed to process and analyze log data using a collaborative agent-based workflow. This repository provides a modular framework integrating various agents, a central orchestration layer, and utility tools to streamline development and deployment.

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)
- [Usage](#usage)
  - [Running the Main Workflow](#running-the-main-workflow)
  - [Managing Prompts with PromptsManager](#managing-prompts-with-promptsmanager)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Overview
This project leverages a multi-agent architecture orchestrated by `graph.py`, supported by configuration management, utility functions, and a robust prompt management system. Key components include:

- **Agents**: Specialized modules for specific tasks (see [agents.md](./doc/agents.md)).
- **Graph**: The main entry point integrating agents into a unified workflow (see [graph.md](./doc/graph.md)).
- **Configurations**: Centralized settings for logging, Docker, and databases (see [configurations.md](./doc/configurable.md)).
- **Utilities**: Helper classes and functions for core functionality (see [utils.md](./doc/utils.md)).
- **Prompt Manager**: A tool to generate, store, manage, and version-control prompts in a JSON file (default: `prompts/prompts.json`, customizable via `-j/--json`), designed for broad use across the project with Git-based version tracking (see [prompt_manager.md](./doc/prompts_manager.md)).

## Installation
1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/logLLM.git
   cd logLLM
   ```

2. **Set Up a Virtual Environment** (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *Note*: `prompts_manager.py` requires only standard Python libraries (`os`, `ast`, `json`, `argparse`, `re`, `inspect`, `subprocess`, `datetime`, and `typing`) but needs `git` installed and accessible in the system PATH for version control features.

4. **Project Structure**:
   ```
   logLLM/
   ├── agents/            # Agent implementations
   ├── prompts/           # Stores prompts.json and test.json (Git-managed)
   ├── utils/             # Utility modules, including prompts_manager.py
   ├── graph.py           # Main workflow orchestration
   ├── config.py          # Configuration settings
   ├── requirements.txt   # Project dependencies
   └── README.md          # This file
   ```

## Usage

### Running the Main Workflow
To execute the core multi-agent system:
```bash
python graph.py
```
See [graph.md](./doc/graph.md) for details.

### Managing Prompts with PromptsManager
The `PromptsManager` (in `utils/prompts_manager.py`) manages prompts in a JSON file (default: `prompts/prompts.json`, customizable with `-j/--json` or `--test`). It provides a public API for use across agents, scripts, and workflows, with Git-based version control to track changes, list version history, revert to previous states, and compare differences between commits.

#### Why Use PromptsManager?
- **Dynamic Prompts**: Retrieve prompts at runtime with `get_prompt`.
- **Centralized Management**: Store and manage prompts in one JSON file.
- **Programmatic Control**: Use `list_prompts`, `add_prompt`, `delete_keys`, `list_versions`, and `revert_version` in your code.
- **Version Control**: Track and revert prompt changes using Git.

#### Quick Start
1. **Initialize the Prompt Store**:
   ```bash
   mkdir -p custom && python utils/prompts_manager.py scan -d agents/ -r -j custom/prompts.json
   ```
   *Note*: This initializes a Git repository in `custom/` if not already present.

2. **List Keys**:
   ```bash
   python utils/prompts_manager.py list --prompt -j custom/prompts.json
   ```

3. **Add a Prompt**:
   ```bash
   python utils/prompts_manager.py add -k agents.module.AgentClass.method -v "Process {data}" -j custom/prompts.json
   ```
   *Note*: Changes are automatically committed to the Git repository in `custom/`.

4. **View Version History**:
   ```bash
   python utils/prompts_manager.py version -k agents.module.AgentClass.method --verbose -1 -j custom/prompts.json
   ```
   **Output**:
   ```
   Version history for 'agents.module.AgentClass.method' in custom/prompts.json:
     - 2025-03-18T10:00:00 | abc12345 | Update prompts.json at 2025-03-18T10:00:00 | Prompt: Process {data}
   ```

5. **Revert a Prompt**:
   ```bash
   python utils/prompts_manager.py revert -c abc12345 -k agents.module.AgentClass.method --verbose -1 -j custom/prompts.json
   ```
   **Output**:
   ```
   Reverted 'agents.module.AgentClass.method' to version from commit abc12345: 'Process {data}'
   Current custom/prompts.json content:
   {...}
   ```

6. **Use in Code**:
   ```python
   from utils.prompts_manager import PromptsManager

   class AgentClass:
       def __init__(self):
           json_path = "custom/prompts.json" if custom else "prompts/prompts.json"
           self.pm = PromptsManager(json_file=json_path)

       def method(self, data):
           # List prompts and versions
           prompts = self.pm.list_prompts(only_prompts=True)
           history = self.pm.list_versions("agents.module.AgentClass.method", verbose=-1)
           print("Prompts:", prompts)
           print("History:", history)
           return self.pm.get_prompt(data=data)

   custom = True  # Toggle for custom file
   agent = AgentClass()
   print(agent.method("log data"))  # "Process log data"
   ```

7. **Delete Keys**:
   ```bash
   python utils/prompts_manager.py delete -k agents.module.AgentClass.method -j custom/prompts.json
   ```

#### CLI Commands
- **Scan**: `python utils/prompts_manager.py scan -d <DIR> [-r] [--hard] [--verbose] [-j PATH] [--test]`
  - Scans a directory, updates the prompt store, and commits changes to Git.
- **List**: `python utils/prompts_manager.py list [--prompt] [--verbose] [-j PATH] [--test]`
  - Lists keys in the prompt store.
- **Add**: `python utils/prompts_manager.py add -k <KEY> -v <VALUE> [--verbose] [-j PATH] [--test]`
  - Adds/updates a prompt and commits to Git.
- **Delete**: `python utils/prompts_manager.py delete -k <KEY1> <KEY2> ... [--verbose] [-j PATH] [--test]`
  - Deletes keys and commits to Git.
- **Version**: `python utils/prompts_manager.py version [-k <KEY>] [--verbose [N]] [-j PATH] [--test]`
  - Lists Git commit history for the file or a key. `--verbose N` shows the first `N` characters of prompts (default: 50; -1 for full).
- **Revert**: `python utils/prompts_manager.py revert -c <HASH> [-k <KEY>] [--verbose [N]] [-j PATH] [--test]`
  - Reverts the file or a key to a commit and commits the revert. `--verbose N` shows the first `N` characters of the reverted prompt (default: 50; -1 for full; non-default also prints full JSON).

#### Customizing with `-j/--json`
Specify a custom JSON file path with `-j/--json` (directory must exist; initialized as a Git repository if not already):
```bash
mkdir -p custom && python utils/prompts_manager.py scan -d agents/ -j custom/prompts.json --verbose
```

#### Testing with `--test`
Use `--test` for `prompts/test.json` (overridden by `-j/--json`):
```bash
python utils/prompts_manager.py scan -d agents/ --test
```

#### Version Control Notes
- The directory containing the JSON file (e.g., `prompts/` or `custom/`) is managed as a separate Git repository.
- To avoid tracking it in the parent `logLLM` repo, add it to `.gitignore`:
  ```
  prompts/
  custom/
  ```
- Alternatively, integrate it as a Git submodule:
  ```bash
  git submodule add <url> prompts
  ```

See [prompt_manager.md](./doc/prompts_manager.md) for full details.

## Documentation
- **[agents.md](./doc/agents.md)**: Agent details.
- **[graph.md](./doc/graph.md)**: Workflow overview.
- **[configurations.md](./doc/configurable.md)**: Config settings.
- **[utils.md](./doc/utils.md)**: Utility documentation.
- **[prompt_manager.md](./doc/prompts_manager.md)**: Prompt management guide, including version control.

## Contributing
Contributions are welcome! Please:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/xyz`).
3. Commit changes (`git commit -m "Add xyz feature"`).
4. Push to the branch (`git push origin feature/xyz`).
5. Open a pull request.

## License
[MIT License](./LICENSE) - feel free to use, modify, and distribute this project.
