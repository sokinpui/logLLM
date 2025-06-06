# Detailed Documentation for Agent-Related Files

This document describes the agents and related utility classes used within the `logLLM` project, primarily located under `src/logllm/agents/`.
For agents specifically involved in the error log analysis and summarization pipeline, please see [doc/error_analysis_agents.md](./error_analysis_agents.md).

---

## File: `src/logllm/agents/agent_abc.py`

### Overview

This file defines the abstract base class `Agent` that serves as an interface for other agent implementations, particularly those using graph-based workflows like LangGraph. It also includes a utility function for state management within LangGraph.

### Class: `Agent(ABC)`

- **Purpose**: Abstract base class defining the common interface for all agents in the system. It enforces the implementation of methods for building a workflow graph (if applicable) and for synchronous/asynchronous execution.
- **Key Attributes**:
  - `graph` (CompiledStateGraph): Expected attribute for agents implementing a LangGraph workflow, holding the compiled graph object.
- **Key Methods**:

  - **`_build_graph(self, typed_state) -> CompiledStateGraph`**
    - **Type**: Abstract Method.
    - **Description**: Intended for subclasses that utilize `langgraph.StateGraph`. This method should be implemented to construct the agent's specific workflow graph, defining nodes and edges based on the provided state type.
    - **Parameters**:
      - `typed_state`: The type definition (typically a `TypedDict`) representing the structure of the agent's state that the graph will operate on.
    - **Returns**: A compiled `langgraph` graph (`CompiledGraph` or similar).
    - **Usage**: Subclasses like `SingleGroupParserAgent` implement this to define their multi-step logic flow.
  - **`run(self)`**
    - **Type**: Abstract Method.
    - **Description**: Defines the primary synchronous execution logic for an agent. Subclasses _must_ implement this method to be runnable.
    - **Parameters**: Varies by implementation (e.g., might take initial state or input data).
    - **Returns**: Varies by implementation (e.g., final state, results dictionary).
    - **Usage**: Called to start the agent's task, e.g., `result = agent.run(input_data)`.
  - **`arun(self)`**
    - **Type**: Abstract Method.
    - **Description**: Defines the primary asynchronous execution logic for an agent. Subclasses _must_ implement this method if asynchronous execution is required.
    - **Parameters**: Varies by implementation.
    - **Returns**: Varies by implementation (awaitable).
    - **Usage**: Called to start the agent's task asynchronously, e.g., `result = await agent.arun(input_data)`.

- **Utility Function**: **`add_string_message(left: list[str], right: str | list[str]) -> list[str]`**
  - **Purpose**: A helper function designed for use with `langgraph` state updates, specifically for fields annotated to accumulate messages. It appends a new string or a list of strings to an existing list within the agent's state.
  - **Parameters**:
    - `left` (list[str]): The current list of messages from the agent's state.
    - `right` (str | list[str]): The new message(s) to be added.
  - **Returns**: (list[str]): The combined list of messages.
  - **Usage**: Often used in `TypedDict` state definitions with `Annotated` types to simplify appending messages during graph execution, e.g., `error_messages: Annotated[list[str], add_string_message]`.

---

## File: `src/logllm/agents/parser_agent.py`

### Overview

This file contains agents focused on parsing log files directly from the local filesystem. It primarily uses the Grok parsing technique, potentially leveraging LLMs for pattern generation, and outputs results to CSV files.

### Class: `SimpleGrokLogParserState(TypedDict)`

- **Purpose**: Defines the data structure (state) passed between steps and returned by the `SimpleGrokLogParserAgent`.
- **Fields**:
  - `log_file_path` (str): The absolute path to the log file being processed.
  - `grok_pattern` (Optional[str]): The Grok pattern string used for parsing. This can be provided initially or generated by the agent.
  - `output_csv_path` (str): The path where the resulting CSV file is saved. Empty if parsing fails or produces no output.
  - `sample_logs` (str): A string containing sample log lines extracted from the file, used as context if the LLM needs to generate a pattern. Populated by the agent.
  - `parsed_lines` (int): A counter for the number of log lines successfully matched and parsed by the Grok pattern.
  - `skipped_lines` (int): A counter for the number of log lines that did _not_ match the Grok pattern.

### Class: `GrokPatternSchema(BaseModel)`

- **Purpose**: A Pydantic data model defining the expected structure for the LLM's response when asked to generate a Grok pattern. This ensures the LLM returns only the pattern string.
- **Fields**:
  - `grok_pattern` (str): The generated Grok pattern string.

### Class: `SimpleGrokLogParserAgent`

- **Purpose**: An agent designed to parse a _single_ log file using a Grok pattern. It can either use a user-provided pattern or generate one using an LLM if none is supplied. The output is a CSV file containing the parsed fields.
- **Key Methods**:
  - **`__init__(self, model: LLMModel)`**
    - **Description**: Initializes the agent. Requires an instance of an `LLMModel` (like `GeminiModel`) for pattern generation and initializes a `PromptsManager` to fetch the necessary prompts.
    - **Parameters**:
      - `model` (LLMModel): The language model instance.
    - **Usage**: `agent = SimpleGrokLogParserAgent(model=my_llm_model)`
  - **`run(self, initial_state: SimpleGrokLogParserState, show_progress: bool = False) -> SimpleGrokLogParserState`**
    - **Description**: The main entry point for parsing a single file. It takes the initial state (requiring `log_file_path`), checks if a `grok_pattern` is present, calls `_generate_grok_pattern` if needed, then calls `_run_grok_parser` to perform the actual parsing and CSV writing.
    - **Parameters**:
      - `initial_state` (SimpleGrokLogParserState): The starting state, must include `log_file_path`, optionally `grok_pattern`.
      - `show_progress` (bool): Flag primarily for compatibility with the group parser; has minimal direct effect on this agent's output.
    - **Returns**: (SimpleGrokLogParserState): The final state containing the `output_csv_path` (if successful), `parsed_lines`, `skipped_lines`, and the `grok_pattern` used.
    - **Usage**: `result = agent.run({"log_file_path": "logs/ssh/SSH.log"})`
  - **`_generate_grok_pattern(self, log_file_path: str) -> Optional[str]`**
    - **Description**: An internal method responsible for generating a Grok pattern using the configured LLM. It reads sample lines from the provided log file, fetches the appropriate prompt using `PromptsManager`, calls the LLM with the samples and the `GrokPatternSchema`, and returns the validated pattern string.
    - **Parameters**:
      - `log_file_path` (str): The path to the log file to sample for context.
    - **Returns**: (Optional[str]): The generated Grok pattern string, or `None` if sampling, LLM call, or validation fails.
    - **Usage**: Called automatically by `run` if `initial_state["grok_pattern"]` is `None`.
  - **`_run_grok_parser(self, state: SimpleGrokLogParserState) -> SimpleGrokLogParserState`**
    - **Description**: An internal method that performs the core Grok parsing. It takes the state (which must now include a valid `grok_pattern`), compiles the pattern using `pygrok.Grok`, reads the input log file line by line, attempts to match each line against the pattern, collects the parsed dictionaries, dynamically determines all unique field names (headers) from the matches, and writes the results to a CSV file named `parsed_grok_<original_basename>.csv` in the same directory as the input file. Updates `parsed_lines` and `skipped_lines` in the state.
    - **Parameters**:
      - `state` (SimpleGrokLogParserState): The state containing `log_file_path` and a valid `grok_pattern`.
    - **Returns**: (SimpleGrokLogParserState): The updated state with `output_csv_path` set upon successful CSV writing, and updated `parsed_lines`/`skipped_lines` counts.
    - **Usage**: Called by `run` after a valid Grok pattern is available.

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

---

## File: `src/logllm/agents/es_parser_agent.py`

### Overview

This file implements a more advanced parsing workflow specifically designed to operate on log data already ingested into Elasticsearch. It uses LangGraph to manage a multi-step process including LLM-based Grok pattern generation, pattern validation, retries on failure, fallback mechanisms, and bulk indexing of results (parsed or original) into separate Elasticsearch indices. It also logs the results of each run to a dedicated history index.

### Class: `ScrollGrokParserState(TypedDict)`

- **Purpose**: Defines the configuration and result structure for the `ScrollGrokParserAgent`, which performs the actual data processing and indexing within Elasticsearch.
- **Fields**:
  - `source_index` (str): The ES index containing the raw log documents to be parsed.
  - `target_index` (str): The ES index where successfully parsed/structured documents will be written.
  - `failed_index` (str): The ES index where documents that failed parsing (or all documents during fallback) will be written.
  - `grok_pattern` (str): The Grok pattern string to be applied to the source documents.
  - `field_to_parse` (str): The name of the field within the source documents that contains the raw log line text (e.g., "content").
  - `source_query` (Optional[Dict]): An optional Elasticsearch query DSL dictionary to filter which documents from the `source_index` should be processed. Defaults to `match_all`.
  - `fields_to_copy` (Optional[List[str]]): An optional list of field names to copy directly from the source document to the target/failed document if they don't already exist after parsing.
  - `batch_size` (int): The number of documents to process and index in each bulk request.
  - `is_fallback_run` (bool): A flag indicating whether this agent run is operating in "fallback" mode (using a generic pattern and writing all source docs to `failed_index`) or "parse" mode (using the provided `grok_pattern` and writing successes to `target_index`, failures to `failed_index`).
  - _Result Fields (Populated by the agent's `run` method)_:
    - `processed_count` (int): Total number of documents scrolled from the source index.
    - `successfully_indexed_count` (int): Number of documents successfully parsed and indexed into the `target_index`.
    - `failed_indexed_count` (int): Number of documents that failed parsing or were part of a fallback run, successfully indexed into the `failed_index`.
    - `parse_error_count` (int): Number of documents that failed the Grok pattern match during a non-fallback run.
    - `index_error_count` (int): Number of errors encountered during Elasticsearch bulk indexing operations (for both target and failed indices).
    - `status` (str): The final status of the agent run ('completed', 'failed').

### Class: `SingleGroupParseGraphState(TypedDict)`

- **Purpose**: Defines the comprehensive state managed by the LangGraph workflow within the `SingleGroupParserAgent`. It holds configuration parameters passed down from the orchestrator and tracks dynamic state across the different nodes of the graph.
- **Fields**:
  - _Configuration_:
    - `group_name` (str): The name of the log group being processed.
    - `source_index` (str): ES index containing raw logs for this group.
    - `target_index` (str): ES index for successfully parsed logs for this group.
    - `failed_index` (str): ES index for failed/fallback logs for this group.
    - `field_to_parse` (str): Field name containing the raw log line.
    - `fields_to_copy` (Optional[List[str]]): Additional fields to copy.
    - `sample_size_generation` (int): Number of samples for LLM pattern generation.
    - `sample_size_validation` (int): Number of samples for validating the generated pattern.
    - `validation_threshold` (float): Success rate (0.0-1.0) required on validation samples.
    - `batch_size` (int): Batch size for bulk indexing operations.
    - `max_regeneration_attempts` (int): Maximum _total_ attempts allowed for pattern generation/validation (includes initial attempt).
    - `keep_unparsed_index` (bool): If `True`, do not delete the `failed_index` before starting the run.
    - `provided_grok_pattern` (Optional[str]): A specific Grok pattern provided by the user via the CLI, bypassing LLM generation.
  - _Dynamic State_:
    - `current_attempt` (int): Tracks the current attempt number for pattern generation/validation (starts at 1).
    - `current_grok_pattern` (Optional[str]): The Grok pattern currently being used or just generated.
    - `last_failed_pattern` (Optional[str]): Stores the pattern from the previous attempt if it failed validation, used as context for retries.
    - `sample_lines_for_generation` (List[str]): Log lines sampled for LLM pattern generation context.
    - `sample_lines_for_validation` (List[str]): Log lines sampled for pattern validation.
    - `validation_passed` (bool): Flag indicating if the `current_grok_pattern` passed the validation step.
    - `final_parsing_status` (str): The overall outcome of the parsing process for this group (e.g., "success", "success_with_errors", "success_fallback", "failed", "failed_fallback"). Set by the final parsing/fallback nodes.
    - `final_parsing_results_summary` (Optional[Dict[str, int]]): A dictionary summarizing the results from the underlying `ScrollGrokParserAgent` run (containing counts like processed, successful, failed, parse_errors, index_errors).
    - `error_messages` (List[str]): A list accumulating error or warning messages encountered during the graph execution.

### Class: `AllGroupsParserState(TypedDict)`

- **Purpose**: Defines the state managed by the `AllGroupsParserAgent`, which orchestrates parsing across multiple log groups.
- **Fields**:
  - `group_info_index` (str): The name of the ES index containing the definitions of log groups and their associated file lists (e.g., `cfg.INDEX_GROUP_INFOS`).
  - `field_to_parse` (str): The field name containing raw log lines (passed down to individual group parsers).
  - `fields_to_copy` (Optional[List[str]]): Additional fields to copy (passed down).
  - `group_results` (Dict[str, SingleGroupParseGraphState]): A dictionary where keys are group names and values are the complete final `SingleGroupParseGraphState` objects returned by the `SingleGroupParserAgent` run for that group. Populated as workers complete.
  - `status` (str): The overall status of the multi-group parsing run ('pending', 'running', 'completed', 'failed').

### Class: `ScrollGrokParserAgent`

- **Purpose**: A lower-level agent responsible for the core task of iterating through documents in a source Elasticsearch index, applying a given Grok pattern (or handling fallback), and indexing the results into appropriate target or failed indices using efficient bulk operations.
- **Key Methods**:
  - **`__init__(self, db: ElasticsearchDatabase)`**
    - **Description**: Initializes the agent with an `ElasticsearchDatabase` instance.
  - **`run(self, state: ScrollGrokParserState) -> ScrollGrokParserState`**
    - **Description**: The main execution method. It takes the configuration state, initializes internal counters and batches, compiles the Grok pattern (if not a fallback run), then uses `db.scroll_and_process_batches` to iterate through source documents. The `_process_batch` method is used as the callback. Finally, it flushes any remaining documents in the internal batches and returns the state updated with processing counts and status.
    - **Parameters**: `state` (ScrollGrokParserState): The configuration defining the source/target indices, pattern, batch size, etc.
    - **Returns**: (ScrollGrokParserState): The input state updated with the results (`processed_count`, `successfully_indexed_count`, `failed_indexed_count`, `parse_error_count`, `index_error_count`, `status`).
  - **`_initialize_grok(self, pattern: str) -> bool`**:
    - **Description**: Attempts to compile the provided Grok pattern string using `pygrok.Grok`. Stores the compiled instance internally.
    - **Returns**: (bool): `True` if compilation succeeds, `False` otherwise.
  - **`_process_single_hit(self, hit: Dict[str, Any], state: ScrollGrokParserState) -> Literal["success", "parse_failed", "skip"]`**:
    - **Description**: Processes a single document (`hit`) retrieved from Elasticsearch. If `is_fallback_run` is True, it immediately adds the original document to the failed batch. Otherwise, it attempts to match the `field_to_parse` against the compiled Grok pattern. If successful, it prepares the parsed document (copying extra fields if needed) and adds it to the success batch. If it fails, it adds the original document to the failed batch.
    - **Returns**: (`Literal["success", "parse_failed", "skip"]`): Status indicating the outcome for this hit.
  - **`_process_batch(self, hits: List[Dict[str, Any]], state: ScrollGrokParserState) -> bool`**:
    - **Description**: Callback function used by `db.scroll_and_process_batches`. It iterates through the provided list of `hits`, calling `_process_single_hit` for each. It updates the agent's internal `_parse_error_count`. If the internal success or failed batches reach the configured `batch_size`, it triggers the corresponding `_flush_..._batch` method.
    - **Returns**: (bool): Always returns `True` to signal that scrolling should continue.
  - **`_flush_success_batch(self, target_index: str)`**:
    - **Description**: Takes the documents accumulated in the internal success batch, formats them as Elasticsearch "update" actions (with `doc_as_upsert: True`), and performs a bulk operation to index them into the `target_index`. Updates `_successfully_indexed_count` and `_index_error_count`. Clears the internal success batch.
  - **`_flush_failed_batch(self, failed_index: str)`**:
    - **Description**: Takes the documents accumulated in the internal failed/fallback batch, formats them as Elasticsearch "index" actions (preserving the original document structure under `original_source` and adding a `failure_reason`), and performs a bulk operation to index them into the `failed_index`. Updates `_failed_indexed_count` and `_index_error_count`. Clears the internal failed batch.

### Class: `SingleGroupParserAgent(Agent)`

- **Purpose**: An agent implementing the `Agent` interface using `langgraph`. It orchestrates the entire parsing process for a _single_ log group within Elasticsearch. This involves potentially generating a Grok pattern via LLM, validating the pattern against sample data, handling retries if validation fails, invoking the `ScrollGrokParserAgent` to perform the actual parsing and indexing (either with the validated pattern or a fallback), and storing the results of the run in a history index (`cfg.INDEX_GROK_RESULTS_HISTORY`).
- **Key Methods**:
  - **`__init__(self, model: LLMModel, db: ElasticsearchDatabase, prompts_manager: PromptsManager)`**
    - **Description**: Initializes the agent with its core dependencies: an `LLMModel` for pattern generation, an `ElasticsearchDatabase` for data access and sampling, and a `PromptsManager` for retrieving prompts. It also instantiates the `ScrollGrokParserAgent` sub-agent and calls `_build_graph` to compile its internal LangGraph workflow.
  - **`run(self, initial_config: Dict[str, Any]) -> SingleGroupParseGraphState`**
    - **Description**: The main entry point for executing the parsing workflow for a single group. It takes a dictionary containing the initial configuration (group name, field names, sizes, thresholds, etc.), converts it into the `SingleGroupParseGraphState` format required by the graph, and then invokes the compiled LangGraph using `self.graph.invoke()`.
    - **Parameters**: `initial_config` (dict): A dictionary containing all necessary configuration parameters for parsing this specific group.
    - **Returns**: (SingleGroupParseGraphState): The final state of the graph after execution, containing the outcome status, results summary, and any accumulated error messages.
  - **`_build_graph(self) -> CompiledGraph`**:
    - **Description**: Defines the structure of the agent's workflow using `langgraph.StateGraph`. It adds nodes corresponding to different logical steps (start, generate, validate, parse, fallback, retry prep, store results) and defines the edges (transitions) between them, including conditional edges based on the state.
    - **Returns**: (CompiledGraph): The compiled LangGraph ready for execution.
  - **Graph Nodes**:
    - **`_start_node`**: Initializes the run. Gets index names, clears the failed index (if `keep_unparsed_index` is False), fetches sample lines for generation (if no pattern provided) and validation from the source index using `db.get_sample_lines`. Sets initial state values.
    - **`_generate_grok_node`**: Called if no pattern was provided or if retrying. Uses the LLM (`self._model.generate`) with the appropriate prompt (fetched via `self._prompts_manager`) and the `GrokPatternSchema` to generate a Grok pattern based on `sample_lines_for_generation` and context from `last_failed_pattern` (if retrying). Updates `current_grok_pattern` in the state.
    - **`_validate_pattern_node`**: Attempts to compile the `current_grok_pattern` using `pygrok.Grok`. If successful, it tests the pattern against the `sample_lines_for_validation` and calculates the success rate. Updates `validation_passed` based on whether the rate meets the `validation_threshold`.
    - **`_parse_all_node`**: Called if validation passes. Configures and runs the `self._scroll_parser_agent` in normal parsing mode (not fallback). Updates `final_parsing_status` and `final_parsing_results_summary` based on the sub-agent's results.
    - **`_fallback_node`**: Called if pattern generation or validation fails after all retries. Configures and runs the `self._scroll_parser_agent` in fallback mode (`is_fallback_run=True`), writing all source documents to the `failed_index`. Updates `final_parsing_status` and `final_parsing_results_summary`.
    - **`_prepare_for_retry_node`**: Called if validation fails but retries remain. Increments the `current_attempt` counter, stores the `current_grok_pattern` into `last_failed_pattern`, and clears `current_grok_pattern` to trigger regeneration in the next loop.
    - **`_store_results_node`**: Called after either `_parse_all_node` or `_fallback_node` completes. It compiles a summary document containing the group name, status, pattern used, timestamp, and result counts, and inserts it into the `cfg.INDEX_GROK_RESULTS_HISTORY` index using `self._db.insert`.
  - **Conditional Edges**:
    - **`_decide_pattern_source`**: Called after `_start_node`. Checks if `provided_grok_pattern` exists in the state. If yes, routes to `validate_pattern`; otherwise, routes to `generate_grok`.
    - **`_decide_after_generate`**: Called after `_generate_grok_node`. Checks if a pattern was successfully generated. If yes, routes to `validate_pattern`. If no, checks if `current_attempt` < `max_regeneration_attempts`; if yes, routes to `prepare_for_retry`; otherwise, routes to `fallback`. Also checks for critical errors like missing validation samples and routes to `fallback`.
    - **`_decide_after_validation`**: Called after `_validate_pattern_node`. Checks if `validation_passed` is True. If yes, routes to `parse_all`. If no, checks if `current_attempt` < `max_regeneration_attempts`; if yes, routes to `prepare_for_retry`; otherwise, routes to `fallback`.

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

---

## File: `src/logllm/utils/chunk_manager.py`

_Note: While located in `utils`, this class is primarily used by analysis agents (not shown in the provided code but relevant context) to handle large text data retrieved from Elasticsearch._

### Class: `ESTextChunkManager`

- **Purpose**: Manages the retrieval and sequential chunking of text data (like log lines associated with a file or event) stored across multiple documents in Elasticsearch. It fetches all relevant documents upfront based on an ID and then provides the text content in manageable chunks that respect LLM token limits.
- **Key Methods**:
  - **`__init__(self, id: Any, field: str, index: str, db: ElasticsearchDatabase)`**
    - **Description**: Initializes the chunk manager. It queries the specified `index` in Elasticsearch using `db.scroll_search` to fetch _all_ documents matching the provided `id`. It stores the retrieved hits (documents) internally.
    - **Parameters**:
      - `id` (Any): The identifier (e.g., file ID, event ID) used in a "match" query to find relevant documents.
      - `field` (str): The name of the field within the ES documents that contains the text content to be chunked (e.g., "content").
      - `index` (str): The Elasticsearch index to query.
      - `db` (ElasticsearchDatabase): An initialized database instance.
    - **Usage**: `chunk_mgr = ESTextChunkManager(id=some_id, field="content", index="my_log_index", db=db_instance)`
  - **`get_next_chunk(self, max_len: int, len_fn: Callable[[str], int]) -> str`**
    - **Description**: Retrieves the next chunk of text. It aggregates the content from the `field` of consecutive hits stored internally, starting from the current position (`self.start`). It uses the `_build_chunk` helper to ensure the total token count of the aggregated text (calculated using `len_fn`) does not exceed `max_len`. After returning a chunk, it updates the internal `start` pointer to the next unread hit.
    - **Parameters**:
      - `max_len` (int): The maximum allowed token length for the returned chunk.
      - `len_fn` (Callable[[str], int]): A function (like `model.token_count`) that takes a string and returns its token count.
    - **Returns**: (str): A string containing the next aggregated chunk of text. Returns an empty string ("") if all hits have been processed.
    - **Usage**: `next_log_chunk = chunk_mgr.get_next_chunk(max_len=10000, len_fn=my_llm.token_count)`
  - **`is_end(self) -> bool`**:
    - **Description**: Checks if all the initially fetched hits have been processed and included in previously returned chunks.
    - **Returns**: (bool): `True` if `self.start` is greater than or equal to the total number of hits, `False` otherwise.
  - **`get_current_chunk(self) -> str | None`**:
    - **Description**: Returns the most recently generated chunk (the one returned by the last call to `get_next_chunk`) without advancing the internal pointer or fetching new data.
    - **Returns**: (str | None): The last generated chunk as a string, or `None` if `get_next_chunk` has not been called yet.
  - **`_build_chunk(self, initial_size: int, start: int, hits: list, max_len: int, len_fn: Callable[[str], int]) -> str`**:
    - **Description**: Internal helper method called by `get_next_chunk`. It iteratively aggregates content from the `hits` list, starting at the `start` index. It dynamically adjusts how many hits are added in each step (`current_size`, initially `initial_size`) to stay under the `max_len` token limit. If adding a block of hits exceeds the limit, it halves `current_size` and retries from the same position. Updates `self.start` and `self.hits_in_current_chunk`.
    - **Returns**: (str): The constructed chunk string.
  - **`_get_all_hits() -> list`**:
    - **Description**: Internal helper method called only by `__init__`. It constructs the Elasticsearch query to match documents based on `self.id` and fetches all matching hits using `self._db.scroll_search`, retrieving only the specified `self.field`.
    - **Returns**: (list): A list of Elasticsearch hit dictionaries (containing `_source` with the specified `field`).

