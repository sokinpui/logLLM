# Project logLLM

**logLLM** is a multi-agent system designed to [insert project purpose, e.g., "process and analyze log data using a collaborative agent-based workflow"]. This repository provides a modular framework integrating various agents, a central orchestration layer, and utility tools to streamline development and deployment.

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

- **Agents**: Specialized modules for specific tasks (see [agents.md](./agents.md)).
- **Graph**: The main entry point integrating agents into a unified workflow (see [graph.md](./graph.md)).
- **Configurations**: Centralized settings for logging, Docker, and databases (see [configurations.md](./configurations.md)).
- **Utilities**: Helper classes and functions for core functionality (see [utils.md](./utils.md)).
- **Prompt Manager**: A tool to generate, store, and manage prompts in `prompts.json` (see [prompt_manager.md](./prompt_manager.md)).

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
   *Note*: Ensure `requirements.txt` includes any dependencies (e.g., none beyond Python standard libraries for `prompts_manager.py`).

4. **Project Structure**:
   ```
   logLLM/
   ├── agents/            # Agent implementations
   ├── prompts/           # Stores prompts.json
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
See [graph.md](./graph.md) for details on how `graph.py` integrates agents and utilizes configurations and utilities.

### Managing Prompts with PromptsManager
The `PromptsManager` (located in `utils/prompts_manager.py`) is a utility for generating, storing, and managing prompts used by agents or other components. It creates and maintains a `prompts.json` file in the `prompts/` directory, mapping Python code structures (directories, modules, classes, functions) to prompt strings.

#### Why Use PromptsManager?
- **Dynamic Prompts**: Agents can retrieve prompts at runtime using `get_prompt`, adapting to code structure changes.
- **Centralized Management**: Store all prompts in a single JSON file, editable manually or via CLI.
- **Synchronization**: Keep `prompts.json` aligned with your codebase using update and hard update features.

#### Quick Start
1. **Initialize `prompts.json`**:
   Scan a directory (e.g., `agents/`) to populate `prompts.json` with your code structure:
   ```bash
   python utils/prompts_manager.py -d agents/ -r
   ```
   This recursively scans `agents/`, adding entries like `"agents.module.AgentClass.method": "no prompts"`.

2. **List All Keys**:
   View the current structure of `prompts.json`:
   ```bash
   python utils/prompts_manager.py list
   ```
   **Output**:
   ```
   Keys in prompts.json:
     - agents
     - agents.module
     - agents.module.AgentClass
     - agents.module.AgentClass.method
   ```

3. **List Prompt Keys Only**:
   See only keys with actual prompts:
   ```bash
   python utils/prompts_manager.py list --prompt
   ```

4. **Add a Prompt**:
   Assign a custom prompt to an existing function:
   ```bash
   python utils/prompts_manager.py add -k agents.module.AgentClass.method -v "Process {data} now"
   ```
   **Output**:
   ```
   Added/Updated prompt for 'agents.module.AgentClass.method': 'Process {data} now'
   ```

5. **Use in Code**:
   Agents can retrieve prompts dynamically:
   ```python
   from utils.prompts_manager import PromptsManager

   class AgentClass:
       def __init__(self):
           self.pm = PromptsManager()

       def method(self, data):
           prompt = self.pm.get_prompt(data="log data")  # Resolves to "agents.module.AgentClass.method"
           print(prompt)  # "Process log data now"

   agent = AgentClass()
   agent.method("log data")
   ```

6. **Synchronize with Code**:
   After modifying code, use a hard update to remove outdated entries:
   ```bash
   python utils/prompts_manager.py -d agents/ -r --hard
   ```

#### CLI Commands
- **Update**: `python utils/prompts_manager.py -d <DIR> [-r]`
  - Adds new entries without removing existing ones.
- **Hard Update**: `python utils/prompts_manager.py -d <DIR> [-r] --hard`
  - Rebuilds the directory’s subtree, preserving prompts for existing objects.
- **List**: `python utils/prompts_manager.py list [--prompt]`
  - Lists all keys or only prompt keys.
- **Add**: `python utils/prompts_manager.py add -k <KEY> -v <VALUE>`
  - Updates an existing prompt key.
- **Delete**: `python utils/prompts_manager.py --delete <KEY1> <KEY2> ...`
  - Removes specified keys.

See [prompt_manager.md](./prompt_manager.md) for detailed API and CLI documentation.

## Documentation
- **[agents.md](./doc/agents.md)**: Details on all agents used in the system.
- **[graph.md](./doc/graph.md)**: Overview of `graph.py` and the multi-agent workflow.
- **[configurations.md](./doc/configurations.md)**: Explanation of `config.py` and its settings.
- **[utils.md](./doc/utils.md)**: Documentation of utility classes and functions.
- **[prompt_manager.md](./doc/prompts_manager.md)**: In-depth guide to `prompts_manager.py`.

