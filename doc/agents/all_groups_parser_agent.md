# All Groups Parser Agent (`es_parser_agent.py`)

## File: `src/logllm/agents/es_parser_agent.py`

### Overview

This document describes the `AllGroupsParserAgent`, which orchestrates the concurrent parsing of multiple log groups within Elasticsearch.

### Class: `AllGroupsParserState(TypedDict)`

- **Purpose**: Defines the state managed by the `AllGroupsParserAgent`, which orchestrates parsing across multiple log groups.
- **Fields**:
  - `group_info_index` (str): The name of the ES index containing the definitions of log groups and their associated file lists (e.g., `cfg.INDEX_GROUP_INFOS`).
  - `field_to_parse` (str): The field name containing raw log lines (passed down to individual group parsers).
  - `fields_to_copy` (Optional[List[str]]): Additional fields to copy (passed down).
  - `group_results` (Dict[str, SingleGroupParseGraphState]): A dictionary where keys are group names and values are the complete final `SingleGroupParseGraphState` objects returned by the `SingleGroupParserAgent` run for that group. Populated as workers complete.
  - `status` (str): The overall status of the multi-group parsing run ('pending', 'running', 'completed', 'failed').

### Class: `AllGroupsParserAgent`

- **Purpose**: An orchestrator agent responsible for managing the concurrent parsing of _all_ log groups found in the Elasticsearch `group_infos` index. It does not perform parsing itself but distributes the work to multiple `SingleGroupParserAgent` instances.
- **Key Methods**:

  - **`__init__(self, model: LLMModel, db: ElasticsearchDatabase, prompts_manager: PromptsManager)`**
    - **Description**: Initializes the orchestrator with shared dependencies (`LLMModel`, `ElasticsearchDatabase`, `PromptsManager`) that will be used by or passed to the worker function.
  - **`run(self, initial_state: AllGroupsParserState, num_threads: int, batch_size: int, ..., keep_unparsed_index: bool, provided_grok_pattern: Optional[str]) -> AllGroupsParserState`**
    - **Description**: The main execution method. It first calls `_get_all_groups` to fetch the list of groups to process. It then prepares a base configuration dictionary containing parameters like batch size, sample sizes, thresholds, etc. For each group, it creates a specific configuration dictionary (adding the `group_name`) and submits a task to a `concurrent.futures.ThreadPoolExecutor` (chosen for I/O-bound sub-tasks) to run the `_parallel_group_worker_new` function. As workers complete, it collects the final `SingleGroupParseGraphState` for each group into the `group_results` dictionary of its own state.
    - **Parameters**:
      - `initial_state` (AllGroupsParserState): Contains `group_info_index`, `field_to_parse`, `fields_to_copy`.
      - `num_threads` (int): Maximum number of concurrent worker threads.
      - `batch_size`, `sample_size`, `validation_sample_size`, `validation_threshold`, `max_regeneration_attempts` (int/float): Configuration parameters passed down to each `SingleGroupParserAgent` worker.
      - `keep_unparsed_index` (bool): Flag passed down to workers.
      - `provided_grok_pattern` (Optional[str]): Pattern passed down (usually `None` for all groups run).
    - **Returns**: (AllGroupsParserState): The final state containing the results (`SingleGroupParseGraphState`) for every processed group in the `group_results` dictionary and an overall `status`.
  - **`_get_all_groups(self, group_info_index: str) -> List[Dict[str, Any]]`**:
    - **Description**: An internal helper method that queries the specified `group_info_index` in Elasticsearch using `db.scroll_search` to retrieve all documents defining log groups.
    - **Returns**: (List[Dict[str, Any]]): A list of dictionaries, where each dictionary represents a group and contains at least the `"group_name"`.

- **Worker Function**: **`_parallel_group_worker_new(single_group_config: Dict[str, Any], prompts_json_path: str) -> Tuple[str, SingleGroupParseGraphState]`**
  - **Purpose**: This function is executed by each thread in the `ThreadPoolExecutor` managed by `AllGroupsParserAgent`. It's responsible for parsing a single log group.
  - **Description**: It initializes its _own_ instances of `ElasticsearchDatabase`, `LLMModel`, and `PromptsManager` (using the provided `prompts_json_path`) to ensure thread safety. It then instantiates a `SingleGroupParserAgent` and calls its `run` method with the `single_group_config` dictionary. It includes error handling to catch exceptions during the agent run and returns a failed state if necessary.
  - **Parameters**:
    - `single_group_config` (Dict): The complete configuration dictionary required by `SingleGroupParserAgent.run` for this specific group.
    - `prompts_json_path` (str): The path to the prompts JSON file, needed to initialize `PromptsManager` within the worker.
  - **Returns**: Tuple `(group_name, final_state_object)`: A tuple containing the name of the processed group and the final `SingleGroupParseGraphState` object returned by the agent's run.
  - **Usage**: Submitted as tasks to the `ThreadPoolExecutor` by `AllGroupsParserAgent.run`.
