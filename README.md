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
- **Prompt Manager**: A tool to generate, store, and manage prompts in a JSON file (default: `prompts/prompts.json`, customizable via `-j/--json`), designed for broad use across the project (see [prompt_manager.md](./doc/prompts_manager.md)).

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
   *Note*: `prompts_manager.py` requires only standard libraries.

4. **Project Structure**:
   ```
   logLLM/
   ├── agents/            # Agent implementations
   ├── prompts/           # Stores prompts.json and test.json
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
The `PromptsManager` (in `utils/prompts_manager.py`) manages prompts in a JSON file (default: `prompts/prompts.json`, customizable with `-j/--json` or `--test`). Its public API is designed for use across agents, scripts, and workflows.

#### Why Use PromptsManager?
- **Dynamic Prompts**: Retrieve prompts at runtime with `get_prompt`.
- **Centralized Management**: Store and manage prompts in one JSON file.
- **Programmatic Control**: Use `list_prompts`, `add_prompt`, and `delete_keys` in your code.

#### Quick Start
1. **Initialize the Prompt Store**:
   ```bash
   mkdir -p custom && python utils/prompts_manager.py scan -d agents/ -r -j custom/prompts.json
   ```

2. **List Keys**:
   ```bash
   python utils/prompts_manager.py list --prompt -j custom/prompts.json
   ```

3. **Add a Prompt**:
   ```bash
   python utils/prompts_manager.py add -k agents.module.AgentClass.method -v "Process {data}" -j custom/prompts.json
   ```

4. **Use in Code**:
   ```python
   from utils.prompts_manager import PromptsManager

   class AgentClass:
       def __init__(self):
           json_path = "custom/prompts.json" if custom else "prompts/prompts.json"
           self.pm = PromptsManager(json_file=json_path)

       def method(self, data):
           prompts = self.pm.list_prompts(only_prompts=True)
           print("Prompts:", prompts)
           return self.pm.get_prompt(data=data)

   custom = True  # Toggle for custom file
   agent = AgentClass()
   print(agent.method("log data"))  # "Process log data"
   ```

5. **Delete Keys**:
   ```bash
   python utils/prompts_manager.py delete -k agents.module.AgentClass.method -j custom/prompts.json
   ```

#### CLI Commands
- **Scan**: `python utils/prompts_manager.py scan -d <DIR> [-r] [--hard] [--verbose] [-j PATH] [--test]`
- **List**: `python utils/prompts_manager.py list [--prompt] [--verbose] [-j PATH] [--test]`
- **Add**: `python utils/prompts_manager.py add -k <KEY> -v <VALUE> [--verbose] [-j PATH] [--test]`
- **Delete**: `python utils/prompts_manager.py delete -k <KEY1> <KEY2> ... [--verbose] [-j PATH] [--test]`

#### Customizing with `-j/--json`
Specify a custom JSON file path with `-j/--json` (directory must exist):
```bash
mkdir -p custom && python utils/prompts_manager.py scan -d agents/ -j custom/prompts.json --verbose
```

#### Testing with `--test`
Use `--test` for `prompts/test.json` (overridden by `-j/--json`):
```bash
python utils/prompts_manager.py scan -d agents/ --test
```

See [prompt_manager.md](./doc/prompts_manager.md) for full details.

## Documentation
- **[agents.md](./doc/agents.md)**: Agent details.
- **[graph.md](./doc/graph.md)**: Workflow overview.
- **[configurations.md](./doc/configurable.md)**: Config settings.
- **[utils.md](./doc/utils.md)**: Utility documentation.
- **[prompt_manager.md](./doc/prompts_manager.md)**: Prompt management guide.


