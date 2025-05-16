# Group Log Parser Agent (`parser_agent.py`)

## File: `src/logllm/agents/parser_agent.py`

### Overview

This document describes the `GroupLogParserAgent`, which orchestrates parsing multiple log files from the local filesystem, grouped by directory structure.

### Class: `GroupLogParserAgent`

- **Purpose**: Orchestrates the parsing of multiple log files, grouped by their parent directory structure (as defined in the Elasticsearch `group_infos` index). It can run sequentially or utilize a pool of worker processes for parallel parsing, delegating the actual parsing of each file to a `SimpleGrokLogParserAgent` instance (via `_parse_file_worker`).
- **Key Methods**:

  - **`__init__(self, model: LLMModel)`**
    - **Description**: Initializes the agent. Requires an `LLMModel` instance (used in the main thread for potential pattern pre-determination or sequential execution) and an `ElasticsearchDatabase` instance to fetch group information.
    - **Parameters**:
      - `model` (LLMModel): The language model instance.
    - **Usage**: `group_agent = GroupLogParserAgent(model=my_llm_model)`
  - **`fetch_groups(self) -> Optional[Dict[str, List[str]]]`**
    - **Description**: Queries the Elasticsearch index defined by `cfg.INDEX_GROUP_INFOS` to retrieve the mapping between group names (e.g., "hadoop", "ssh") and the list of absolute file paths belonging to each group.
    - **Returns**: (Optional[Dict[str, List[str]]]): A dictionary where keys are group names and values are lists of file paths, or `None` if the index doesn't exist or an error occurs.
    - **Usage**: Called at the beginning of the `run` method.
  - **`parse_all_logs(self, groups: Dict[str, List[str]], num_threads: int, show_progress: bool) -> Dict[str, List[str]]]`**
    - **Description**: The core logic for parsing multiple groups. It first attempts to pre-determine a Grok pattern for each group by sampling the first available log file in that group (using `SimpleGrokLogParserAgent._generate_grok_pattern`). Then, it creates a list of tasks (group, file path). Based on `num_threads`, it either iterates through tasks sequentially (calling `SimpleGrokLogParserAgent.run` directly) or submits tasks to a `concurrent.futures.ProcessPoolExecutor`, executing the `_parse_file_worker` function for each task. It collects the paths of successfully generated CSV files for each group.
    - **Parameters**:
      - `groups` (Dict[str, List[str]]): The dictionary mapping groups to file paths, obtained from `fetch_groups`.
      - `num_threads` (int): The number of worker processes to use (1 for sequential execution).
      - `show_progress` (bool): Controls whether detailed status is printed per file (useful for parallel) or if a simple progress bar is shown (only for sequential).
    - **Returns**: (Dict[str, List[str]]): A dictionary mapping group names to a list of paths of the successfully created output CSV files for that group.
    - **Usage**: Called internally by the `run` method.
  - **`_update_progress_bar(self, current: int, total: int, current_file: str = "", force_newline: bool = False)`**
    - **Description**: A simple helper method to display an overwriting progress bar in the console during sequential execution when `show_progress` is `False`.
    - **Parameters**: Counters, current file name for display.
    - **Usage**: Called within the sequential loop in `parse_all_logs`.
  - **`run(self, num_threads: int = 1, show_progress: bool = False) -> dict`**
    - **Description**: The main public entry point for the group parser agent. It first calls `fetch_groups` to get the work definition and then calls `parse_all_logs` to execute the parsing workflow.
    - **Parameters**:
      - `num_threads` (int): Number of parallel worker processes to use (defaults to 1).
      - `show_progress` (bool): Controls the level of progress display during parsing (defaults to False).
    - **Returns**: (dict): The results dictionary returned by `parse_all_logs`, mapping group names to lists of output CSV paths.
    - **Usage**: `results = group_agent.run(num_threads=4, show_progress=True)`

- **Worker Function**: **`_parse_file_worker(file_path: str, group_grok_pattern: Optional[str], show_progress: bool) -> Tuple[str, Optional[str]]`**
  - **Purpose**: This function is designed to be executed by worker processes created by `ProcessPoolExecutor` in `GroupLogParserAgent.parse_all_logs`. It handles the parsing of a single log file.
  - **Description**: Initializes its own `LLMModel` and `SimpleGrokLogParserAgent`. It attempts to parse the given `file_path` using the `group_grok_pattern` (if provided). If parsing fails _and_ a group pattern was provided, it attempts a fallback by calling the agent again without a pattern, forcing LLM generation specific to that file.
  - **Parameters**:
    - `file_path` (str): The absolute path of the log file to be parsed by this worker.
    - `group_grok_pattern` (Optional[str]): The Grok pattern pre-determined for the group this file belongs to (can be `None`).
    - `show_progress` (bool): Passed down from the main agent, less relevant for worker output but used for consistency.
  - **Returns**: Tuple `(original_file_path, output_csv_path or None)`: A tuple containing the original input file path and the path to the generated CSV file (or `None` if parsing failed).
  - **Usage**: Submitted as tasks to the `ProcessPoolExecutor` by `GroupLogParserAgent`.
